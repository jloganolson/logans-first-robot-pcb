#include "stm32f0xx.h"
#include "tusb.h"
#include "device/dcd.h"
#include "controller.h"
#include <string.h>
#include <errno.h>

static volatile uint32_t milliseconds;
static volatile bool usb_fault;
static volatile bool hardware_armed;
static volatile uint32_t hardware_last_ms;
static pwm_controller control;
static char line[PWM_LINE_MAX];
static size_t used;
static bool overflow;
uint32_t SystemCoreClock=48000000;

static void outputs_off(void){GPIOB->BSRR=GPIO_BSRR_BR_1;TIM3->CCER=0;hardware_armed=false;}
static void fatal(void){outputs_off();for(;;){}}
void SysTick_Handler(void){
    ++milliseconds;
    /* Independent of USB parsing: drop OE even if the foreground is blocked. */
    if(hardware_armed&&(uint32_t)(milliseconds-hardware_last_ms)>=PWM_WATCHDOG_MS){
        outputs_off();usb_fault=true;
    }
}
uint32_t tusb_time_millis_api(void){return milliseconds;}
void USB_IRQHandler(void){tud_int_handler(0);}
void tud_event_hook_cb(uint8_t rhport,uint32_t event,bool in_isr){
    (void)rhport;(void)in_isr;
    if(event==DCD_EVENT_BUS_RESET_START||event==DCD_EVENT_BUS_RESET_END||
       event==DCD_EVENT_UNPLUGGED||event==DCD_EVENT_SUSPEND){outputs_off();usb_fault=true;}
}
static void disconnected(void){
    outputs_off();pwm_connection(&control,false);used=0;overflow=false;
}
void tud_mount_cb(void){disconnected();}
void tud_umount_cb(void){disconnected();}
void tud_suspend_cb(bool remote_wakeup_en){(void)remote_wakeup_en;disconnected();}
void tud_resume_cb(void){disconnected();}
void tud_cdc_line_state_cb(uint8_t itf,bool dtr,bool rts){
    (void)itf;(void)rts;disconnected();
    if(dtr&&!tud_suspended())pwm_connection(&control,true);
}
static void hardware_init(void){
    RCC->AHBENR|=RCC_AHBENR_GPIOAEN|RCC_AHBENR_GPIOBEN|RCC_AHBENR_GPIOFEN;
    GPIOB->BSRR=GPIO_BSRR_BR_1;
    GPIOB->MODER=(GPIOB->MODER&~(3u<<2))|(1u<<2); /* PB1/OE gate default LOW */
    /* Start independent watchdog before waiting for the crystal. PR=16,
     * RLR=249 =>4000 LSI periods:80–133.4ms at DS9826 Table44's30–50kHz
     * LSI range (VDDA3.3V). Still measure the actual reset/enable timing. */
    IWDG->KR=0xcccc; /* Starting watchdog also starts its LSI clock. */
    IWDG->KR=0x5555;IWDG->PR=2;IWDG->RLR=249;
    while(IWDG->SR){} IWDG->KR=0xaaaa;
    FLASH->ACR=FLASH_ACR_PRFTBE|FLASH_ACR_LATENCY;
    RCC->CR|=RCC_CR_HSEON;while(!(RCC->CR&RCC_CR_HSERDY)){}
    RCC->CFGR2=0; /* HSE/PREDIV1 */
    RCC->CFGR=(RCC->CFGR&~(RCC_CFGR_PLLSRC|RCC_CFGR_PLLMUL|RCC_CFGR_HPRE|RCC_CFGR_PPRE))|
        RCC_CFGR_PLLSRC_HSE_PREDIV|RCC_CFGR_PLLMUL6;
    RCC->CR|=RCC_CR_PLLON;while(!(RCC->CR&RCC_CR_PLLRDY)){}
    RCC->CFGR=(RCC->CFGR&~RCC_CFGR_SW)|RCC_CFGR_SW_PLL;
    while((RCC->CFGR&RCC_CFGR_SWS)!=RCC_CFGR_SWS_PLL){}
    RCC->CFGR3|=RCC_CFGR3_USBSW; /* USB=PLL48MHz, not HSI48 */
    RCC->CR|=RCC_CR_CSSON; /* HSE loss => NMI => outputs disabled */
    RCC->APB1ENR|=RCC_APB1ENR_TIM3EN|RCC_APB1ENR_USBEN;
    /* PA6/PA7/PB0 AF1. PA11/12 USB use embedded PHY/pull-up. */
    GPIOA->AFR[0]=(GPIOA->AFR[0]&~((15u<<24)|(15u<<28)))|(1u<<24)|(1u<<28);
    GPIOB->AFR[0]=(GPIOB->AFR[0]&~15u)|1u;
    GPIOA->MODER=(GPIOA->MODER&~((3u<<12)|(3u<<14)))|(2u<<12)|(2u<<14);
    GPIOB->MODER=(GPIOB->MODER&~3u)|2u;
    TIM3->PSC=47;TIM3->ARR=19999;
    TIM3->CCR1=0;TIM3->CCR2=0;TIM3->CCR3=0;
    TIM3->CCMR1=(6u<<4)|TIM_CCMR1_OC1PE|(6u<<12)|TIM_CCMR1_OC2PE;
    TIM3->CCMR2=(6u<<4)|TIM_CCMR2_OC3PE;
    TIM3->CR1=TIM_CR1_ARPE;TIM3->EGR=TIM_EGR_UG;TIM3->CR1|=TIM_CR1_CEN;
    outputs_off();SysTick_Config(48000);
    NVIC_SetPriority(USB_IRQn,1);NVIC_SetPriority(SysTick_IRQn,0);
}
static void apply_outputs(void){
    /* Prevent update between the three writes: preload transfers on the next
     * frame. UDIS holds pending update events until all CCRs are ready. */
    uint32_t irq=__get_PRIMASK();__disable_irq();
    if(usb_fault||!control.armed){outputs_off();}
    else {
        hardware_last_ms=control.last_ms;
        TIM3->CR1|=TIM_CR1_UDIS;
        TIM3->CCR1=control.widths[0];TIM3->CCR2=control.widths[1];TIM3->CCR3=control.widths[2];
        TIM3->CR1&=~TIM_CR1_UDIS;
        if(!TIM3->CCER){
            /* Initial ARM begins a full, deliberate frame with the staged
             * widths; subsequent updates transfer at natural frame boundaries. */
            TIM3->EGR=TIM_EGR_UG;TIM3->SR=0;
            TIM3->CCER=TIM_CCER_CC1E|TIM_CCER_CC2E|TIM_CCER_CC3E;
            GPIOB->BSRR=GPIO_BSRR_BS_1;
            hardware_armed=true;
        }
    }
    __set_PRIMASK(irq);
}
/* This controller has no heap. Refuse accidental libc allocation explicitly. */
void *_sbrk(int increment){(void)increment;errno=ENOMEM;return (void*)-1;}
static void receive(void){
    /* Strict bounded framing, <=64bytes per foreground turn. Overlong line is
     * discarded to newline; it never refreshes watchdog or changes a channel. */
    char reply[96];unsigned budget=64;
    while(budget--&&tud_cdc_available()){
        char c=(char)tud_cdc_read_char();
        if(c=='\r')continue;
        if(c=='\n'){
            line[used]=0;
            if(!overflow&&used){pwm_command(&control,line,milliseconds,reply,sizeof(reply));apply_outputs();
                if(tud_cdc_write_available()>=strlen(reply))tud_cdc_write(reply,strlen(reply));}
            used=0;overflow=false;
        }else if((unsigned char)c<32||(unsigned char)c>126){overflow=true;}
        else if(used<sizeof(line)-1)line[used++]=c;else overflow=true;
    }
    tud_cdc_write_flush();
}
int main(void){
    hardware_init();
    const uint32_t *uid=(const uint32_t*)UID_BASE;
    pwm_init(&control,uid[0]^uid[1]^uid[2]);
    const tusb_rhport_init_t init={.role=TUSB_ROLE_DEVICE,.speed=TUSB_SPEED_FULL};
    if(!tusb_init(0,&init))fatal();
    for(;;){
        tud_task();
        if(usb_fault){
            uint32_t irq=__get_PRIMASK();__disable_irq();
            disconnected();usb_fault=false;__set_PRIMASK(irq);
            /* A new DTR edge or deliberately reopened connection is required. */
        }
        pwm_tick(&control,milliseconds);apply_outputs();receive();
        IWDG->KR=0xaaaa;
    }
}

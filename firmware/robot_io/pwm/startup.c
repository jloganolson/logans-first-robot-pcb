#include <stdint.h>
#include "stm32f0xx.h"
extern uint32_t _estack,_sidata,_sdata,_edata,_sbss,_ebss;
extern int main(void);
extern void SysTick_Handler(void),USB_IRQHandler(void);
void Default_Handler(void){
    /* Hard fault/NMI must cut buffer enable before waiting for watchdog. */
    RCC->AHBENR|=RCC_AHBENR_GPIOBEN; GPIOB->BSRR=GPIO_BSRR_BR_1;
    GPIOB->MODER=(GPIOB->MODER&~(3u<<2))|(1u<<2);
    for(;;){}
}
void Reset_Handler(void){
    uint32_t *src=&_sidata;
    for(uint32_t *p=&_sdata;p<&_edata;) *p++=*src++;
    for(uint32_t *p=&_sbss;p<&_ebss;) *p++=0;
    main();Default_Handler();
}
typedef void(*handler)(void);
__attribute__((used,section(".vectors"))) const handler vectors[48]={
    [0]=(handler)&_estack,[1]=Reset_Handler,[2]=Default_Handler,[3]=Default_Handler,
    [11]=Default_Handler,[14]=Default_Handler,[15]=SysTick_Handler,
    [16 ... 46]=Default_Handler,[47]=USB_IRQHandler
};

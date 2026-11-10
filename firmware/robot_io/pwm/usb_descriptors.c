/* Project prototype identity only: TinyUSB example VID/PID is not an assigned
 * product identity. Obtain an authorized identity before product distribution. */
#include <string.h>
#include "stm32f0xx.h"
#include "tusb.h"
static const tusb_desc_device_t device={
    .bLength=sizeof(tusb_desc_device_t),.bDescriptorType=TUSB_DESC_DEVICE,.bcdUSB=0x0200,
    .bDeviceClass=TUSB_CLASS_MISC,.bDeviceSubClass=MISC_SUBCLASS_COMMON,
    .bDeviceProtocol=MISC_PROTOCOL_IAD,.bMaxPacketSize0=64,
    .idVendor=0xcafe,.idProduct=0x4011,.bcdDevice=0x0100,
    .iManufacturer=1,.iProduct=2,.iSerialNumber=3,.bNumConfigurations=1
};
const uint8_t *tud_descriptor_device_cb(void){return (const uint8_t*)&device;}
static const uint8_t config[]={
    /* MCU and logic are VBUS powered; separate servo rail is not USB load.
     * 100mA is a conservative declared prototype budget, to be measured. */
    TUD_CONFIG_DESCRIPTOR(1,2,0,TUD_CONFIG_DESC_LEN+TUD_CDC_DESC_LEN,0,100),
    TUD_CDC_DESCRIPTOR(0,4,0x81,8,0x02,0x82,64)
};
const uint8_t *tud_descriptor_configuration_cb(uint8_t i){return i?NULL:config;}
const uint16_t *tud_descriptor_string_cb(uint8_t i,uint16_t lang){
    (void)lang; static uint16_t out[33];
    const char *s=NULL; char serial[25];
    static const char *const names[]={NULL,"Robot prototype","Robot three-channel PWM",NULL,"Servo control"};
    if(i==0){out[1]=0x0409;out[0]=(TUSB_DESC_STRING<<8)|4;return out;}
    if(i==3){
        static const char hex[]="0123456789ABCDEF";
        const uint8_t *uid=(const uint8_t*)UID_BASE;
        for(unsigned j=0;j<12;j++){serial[j*2]=hex[uid[j]>>4];serial[j*2+1]=hex[uid[j]&15];}
        serial[24]=0;s=serial;
    }else if(i<sizeof(names)/sizeof(names[0]))s=names[i];
    if(!s)return NULL;
    size_t len=strlen(s);if(len>32)len=32;
    for(size_t j=0;j<len;j++)out[j+1]=(uint8_t)s[j];
    out[0]=(uint16_t)((TUSB_DESC_STRING<<8)|(2*len+2));return out;
}

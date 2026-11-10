#include "controller.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static pwm_controller s;
static char reply[96],cmd[128];
static void send(const char *p,uint32_t t){pwm_command(&s,p,t,reply,sizeof(reply));}
static void session(uint32_t t){
    pwm_connection(&s,true);send("INFO",t);assert(s.token&&!s.armed);
    snprintf(cmd,sizeof(cmd),"STAGE %lu 1 1000 1500 2000",(unsigned long)s.token);send(cmd,t);
    assert(s.staged&&!s.armed);
    snprintf(cmd,sizeof(cmd),"ARM %lu 2",(unsigned long)s.token);send(cmd,t);assert(s.armed);
}
int main(void){
    pwm_init(&s,123);send("ARM 1 1",0);assert(!s.armed);
    session(100);uint32_t token=s.token;
    snprintf(cmd,sizeof(cmd),"SET %lu 3 1500 1500 2500",(unsigned long)token);send(cmd,110);
    assert(!strncmp(reply,"ERR RANGE",9)&&s.widths[0]==1000&&s.last_ms==100);
    snprintf(cmd,sizeof(cmd),"KEEP %lu 2",(unsigned long)token);send(cmd,120);assert(s.last_ms==100);
    pwm_tick(&s,599);assert(s.armed);pwm_tick(&s,600);assert(!s.armed&&!s.token);
    session(UINT32_MAX-100);pwm_tick(&s,398);assert(s.armed);pwm_tick(&s,399);assert(!s.armed);
    session(1000);token=s.token;pwm_connection(&s,false);assert(!s.armed&&!s.token);
    pwm_connection(&s,true);snprintf(cmd,sizeof(cmd),"ARM %lu 3",(unsigned long)token);send(cmd,1010);assert(!s.armed);
    session(1100);token=s.token;send("INFO",1101);assert(!s.armed&&s.token!=token);
    session(1200);
    const char *bad[]={"", "ARM", "ARM 1 1 x", "SET -1 3 1500 1500 1500", "SET 4294967296 3 1500 1500 1500", "SET  1 3 1500 1500 1500", "KEEP 0 9", "STAGE 1 9 1500 1500 1500"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++){uint32_t last=s.last_ms;send(bad[i],1210);assert(s.last_ms==last);}
    /* Bounded deterministic malformed-stream fuzz: never refresh timeout. */
    uint32_t rng=1;
    for(unsigned k=0;k<100000;k++){
        unsigned len=k%95;for(unsigned j=0;j<len;j++){rng=rng*1664525u+1013904223u;cmd[j]=(char)(33+(rng%94));}cmd[len]=0;
        uint32_t last=s.last_ms;send(cmd,1250);assert(s.last_ms==last);
    }
    send("DISARM",1251);assert(!s.armed&&!s.token);
    puts("controller: valid flow, atomic range rejection, stale tokens/sequences, rollover timeout, disconnect and100000 malformed lines passed");
}

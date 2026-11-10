#include "controller.h"
#include <stdio.h>
#include <string.h>
#include <limits.h>

void pwm_init(pwm_controller *s, uint32_t seed) {
    memset(s, 0, sizeof(*s)); s->generation=seed ? seed : 1u;
}
void pwm_disarm(pwm_controller *s) {
    s->armed=false; s->staged=false; s->token=0; s->sequence=0;
}
void pwm_connection(pwm_controller *s, bool connected) {
    pwm_disarm(s); s->connected=connected;
}
void pwm_tick(pwm_controller *s, uint32_t now) {
    if (s->armed && (uint32_t)(now-s->last_ms)>=PWM_WATCHDOG_MS) pwm_disarm(s);
}
/* Strict unsigned decimal grammar; no signs, overflow, extra fields or quoting. */
static bool number(const char *p, uint32_t *v) {
    if (!*p) return false;
    uint32_t a=0;
    for (; *p; ++p) {
        if (*p<'0'||*p>'9'||a>(UINT32_MAX-(uint32_t)(*p-'0'))/10u) return false;
        a=a*10u+(uint32_t)(*p-'0');
    }
    *v=a; return true;
}
void pwm_command(pwm_controller *s, const char *line, uint32_t now, char *reply, size_t n) {
    pwm_tick(s,now);
    if (!strcmp(line,"DISARM")) { pwm_disarm(s); snprintf(reply,n,"OK DISARM\n"); return; }
    if (!s->connected) { snprintf(reply,n,"ERR DISCONNECTED\n"); return; }
    if (!strcmp(line,"INFO")) {
        /* INFO always creates a new disarmed session. Token prevents accidental
         * buffered commands crossing a connection; it is not authentication. */
        pwm_disarm(s);
        s->generation=s->generation*1664525u+1013904223u+now;
        s->token=s->generation ? s->generation : 1u;
        snprintf(reply,n,"OK INFO 1 %lu DISARMED\n",(unsigned long)s->token); return;
    }
    char buf[PWM_LINE_MAX], *fields[7]; unsigned count=0;
    if (strlen(line)>=sizeof(buf)) { snprintf(reply,n,"ERR LENGTH\n"); return; }
    strcpy(buf,line);
    char *p=buf;
    while (*p && count<7) {
        fields[count++]=p;
        while (*p && *p!=' ') ++p;
        if (*p) { *p++=0; if (!*p || *p==' ') { count=7; break; } }
    }
    uint32_t v[5]={0};
    if (*p || count<3 || count>6) { snprintf(reply,n,"ERR SYNTAX\n"); return; }
    for (unsigned i=1;i<count;i++) if (!number(fields[i],&v[i-1])) { snprintf(reply,n,"ERR SYNTAX\n"); return; }
    if (!s->token || v[0]!=s->token) { snprintf(reply,n,"ERR TOKEN\n"); return; }
    /* Deliberately no sequence wrap within a session; INFO starts a new one. */
    if (v[1]<=s->sequence) { snprintf(reply,n,"ERR SEQUENCE\n"); return; }
    bool stage=!strcmp(fields[0],"STAGE"), set=!strcmp(fields[0],"SET");
    if ((stage||set) && count==6) {
        if ((stage && s->armed)||(set && !s->armed)) { snprintf(reply,n,"ERR STATE\n"); return; }
        for (unsigned i=2;i<5;i++) if (v[i]<1000 || v[i]>2000) { snprintf(reply,n,"ERR RANGE\n"); return; }
        for (unsigned i=0;i<3;i++) s->widths[i]=(uint16_t)v[i+2];
        s->staged=true;
    } else if (!strcmp(fields[0],"ARM") && count==3) {
        if (s->armed || !s->staged) { snprintf(reply,n,"ERR STATE\n"); return; }
        s->armed=true;
    } else if (!strcmp(fields[0],"KEEP") && count==3) {
        if (!s->armed) { snprintf(reply,n,"ERR STATE\n"); return; }
    } else { snprintf(reply,n,"ERR SYNTAX\n"); return; }
    s->sequence=v[1]; s->last_ms=now;
    snprintf(reply,n,"OK %s %lu\n",fields[0],(unsigned long)s->sequence);
}

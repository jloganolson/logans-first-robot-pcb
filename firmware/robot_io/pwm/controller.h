#ifndef ROBOT_PWM_CONTROLLER_H
#define ROBOT_PWM_CONTROLLER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define PWM_WATCHDOG_MS 500u
#define PWM_LINE_MAX 96u
typedef struct {
    bool armed, staged, connected;
    uint32_t token, sequence, last_ms, generation;
    uint16_t widths[3];
} pwm_controller;
void pwm_init(pwm_controller *s, uint32_t seed);
void pwm_disarm(pwm_controller *s);
void pwm_connection(pwm_controller *s, bool connected);
void pwm_tick(pwm_controller *s, uint32_t now);
void pwm_command(pwm_controller *s, const char *line, uint32_t now, char *reply, size_t n);
#endif

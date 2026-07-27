#ifndef ROTT64_N64_PLATFORM_H
#define ROTT64_N64_PLATFORM_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __N64__
/* ROTT64_R104_PRESENT_WRAPPER_VOID_DECL
 * Do not include libdragon.h from this public platform header.
 * Generated ROTT files may include signal.h first; libdragon's
 * ucontext.h can then collide on stack_t. Use void* here and cast
 * inside n64_platform.c, where libdragon.h is already safe.
 */
void rott64_n64_display_show_crt_safe(void *surface);
#endif

void n64_platform_init(void);
void n64_platform_fatal(const char *message);
void n64_platform_checkpoint(const char *message);
uint64_t n64_platform_ticks_ms(void);
void n64_platform_wait_ms(uint32_t milliseconds);
void n64_platform_poll(void);
void n64_platform_rumble_pulse(uint32_t duration_ms, uint8_t strength);
void n64_platform_rumble_stop(void);

#endif

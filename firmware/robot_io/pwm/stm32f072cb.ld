ENTRY(Reset_Handler)
MEMORY { FLASH (rx): ORIGIN = 0x08000000,LENGTH = 128K
         RAM (rwx): ORIGIN = 0x20000000,LENGTH = 16K }
_estack = ORIGIN(RAM)+LENGTH(RAM);
SECTIONS {
 .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) .  =  ALIGN(4); } > FLASH
 .ARM.exidx : { *(.ARM.exidx*) } > FLASH
 _sidata = LOADADDR(.data);
 .data : { .  =  ALIGN(4); _sdata = .; *(.data*) .  =  ALIGN(4); _edata = .; } > RAM AT > FLASH
 .bss : { .  =  ALIGN(4); _sbss = .; *(.bss*) *(COMMON) .  =  ALIGN(4); _ebss = .; } > RAM
 .stack (ORIGIN(RAM) + LENGTH(RAM) - 2048) (NOLOAD) : { . = ALIGN(8); . += 2048; } > RAM
 /DISCARD/ : { *(.comment*) *(.note*) }
}

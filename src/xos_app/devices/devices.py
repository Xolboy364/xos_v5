"""
xOS Devices — Virtual Qurilmalar
===================================
Barcha qurilmalar xotiraga mapped (MMIO):

  0xFF000000 – UART    (serial port)
  0xFF001000 – Timer   (hardware timer)
  0xFF002000 – GPIO    (general purpose I/O)
  0xFF003000 – Display (framebuffer)
  0xFF004000 – DMA     (direct memory access)
  0xFF005000 – PIC     (interrupt controller)
  0xFF006000 – RTC     (real-time clock)
  0xFF007000 – SPI     (SPI bus)
  0xFF008000 – I2C     (I2C bus)
  0xFF009000 – SD      (storage)
"""

import time
import math
import struct
from collections import deque

# ── Base manzillar ──────────────────────────────────────
UART_BASE    = 0xFF000000
TIMER_BASE   = 0xFF001000
GPIO_BASE    = 0xFF002000
DISPLAY_BASE = 0xFF003000
DMA_BASE     = 0xFF004000
PIC_BASE     = 0xFF005000
RTC_BASE     = 0xFF006000
SPI_BASE     = 0xFF007000
I2C_BASE     = 0xFF008000
SD_BASE      = 0xFF009000

# ── UART registrlari (offset) ───────────────────────────
UART_DATA    = 0x00   # R/W: ma'lumot
UART_STATUS  = 0x04   # R:   holat (bit0=TX_READY, bit1=RX_READY)
UART_CTRL    = 0x08   # W:   boshqaruv
UART_BAUD    = 0x0C   # W:   baud rate
UART_FIFO    = 0x10   # R:   FIFO holati

# ── Timer registrlari ───────────────────────────────────
TIMER_LOAD   = 0x00
TIMER_VALUE  = 0x04
TIMER_CTRL   = 0x08   # bit0=enable, bit1=irq_enable, bit2=periodic
TIMER_IRQ    = 0x0C   # W: 1 yozsa IRQ tozalanadi
TIMER_PRESCL = 0x10   # Prescaler

# ── GPIO registrlari ────────────────────────────────────
GPIO_DIR     = 0x00   # 0=kirish, 1=chiqish
GPIO_OUT     = 0x04   # Chiqish qiymati
GPIO_IN      = 0x08   # Kirish qiymati (o'qish)
GPIO_IRQ_EN  = 0x0C   # IRQ ruxsati
GPIO_IRQ_ST  = 0x10   # IRQ holati
GPIO_PULL    = 0x14   # Pull-up/down
GPIO_ALT     = 0x18   # Alternate function

# ── Display registrlari ─────────────────────────────────
DISPLAY_W    = 0x00
DISPLAY_H    = 0x04
DISPLAY_BPP  = 0x08
DISPLAY_CTRL = 0x0C
DISPLAY_FB   = 0x10   # Framebuffer boshlanish manzili

# ── PIC registrlari ─────────────────────────────────────
PIC_MASK     = 0x00
PIC_STATUS   = 0x04
PIC_PENDING  = 0x08
PIC_EOI      = 0x0C   # End of interrupt

# ── IRQ raqamlari ───────────────────────────────────────
IRQ_UART     = 0
IRQ_TIMER    = 1
IRQ_GPIO     = 2
IRQ_DMA      = 3
IRQ_SPI      = 4
IRQ_I2C      = 5
IRQ_SD       = 6


# ═══════════════════════════════════════════════════════
# UART — Serial Port
# ═══════════════════════════════════════════════════════

class UART:
    """
    To'liq UART emulyatori.
    TX/RX FIFO, baud rate, IRQ.
    """

    FIFO_SIZE = 256

    def __init__(self):
        self.tx_fifo    = deque(maxlen=self.FIFO_SIZE)
        self.rx_fifo    = deque(maxlen=self.FIFO_SIZE)
        self.baud_rate  = 115200
        self.enabled    = True
        self.irq_enable = False
        self.irq_pending= False
        self._output_cb = None
        self._log       = []

    def write_reg(self, offset: int, val: int):
        if offset == UART_DATA:
            ch = chr(val & 0xFF)
            self.tx_fifo.append(ch)
            self._log.append(ch)
            if self._output_cb:
                self._output_cb(ch)
            if self.irq_enable:
                self.irq_pending = True

        elif offset == UART_CTRL:
            self.enabled    = bool(val & 1)
            self.irq_enable = bool(val & 2)

        elif offset == UART_BAUD:
            self.baud_rate = max(1200, min(4000000, val))

    def read_reg(self, offset: int) -> int:
        if offset == UART_DATA:
            if self.rx_fifo:
                return ord(self.rx_fifo.popleft())
            return 0

        elif offset == UART_STATUS:
            tx_ready = 1 if len(self.tx_fifo) < self.FIFO_SIZE else 0
            rx_ready = 1 if self.rx_fifo else 0
            return tx_ready | (rx_ready << 1)

        elif offset == UART_FIFO:
            return len(self.tx_fifo) | (len(self.rx_fifo) << 16)

        return 0

    def feed_rx(self, text: str):
        """Tashqaridan ma'lumot kiritish."""
        for ch in text:
            self.rx_fifo.append(ch)

    def set_output_callback(self, cb):
        self._output_cb = cb

    def get_output(self) -> str:
        return "".join(self._log)

    def clear_output(self):
        self._log.clear()

    def tick(self):
        if self.irq_pending:
            self.irq_pending = False
            return IRQ_UART
        return None


# ═══════════════════════════════════════════════════════
# TIMER — Hardware Timer
# ═══════════════════════════════════════════════════════

class Timer:
    """
    Dasturiy timer.
    Periodic va one-shot rejimi, IRQ.
    """

    def __init__(self, timer_id: int = 0):
        self.id         = timer_id
        self.load_val   = 0
        self.value      = 0
        self.enabled    = False
        self.irq_enable = False
        self.periodic   = False
        self.prescaler  = 1
        self.irq_pending= False
        self._ticks     = 0
        self._fire_count= 0

    def write_reg(self, offset: int, val: int):
        if offset == TIMER_LOAD:
            self.load_val = val
            self.value    = val

        elif offset == TIMER_CTRL:
            self.enabled    = bool(val & 1)
            self.irq_enable = bool(val & 2)
            self.periodic   = bool(val & 4)
            if self.enabled and self.value == 0:
                self.value = self.load_val

        elif offset == TIMER_IRQ:
            if val & 1:
                self.irq_pending = False

        elif offset == TIMER_PRESCL:
            self.prescaler = max(1, val)

    def read_reg(self, offset: int) -> int:
        if offset == TIMER_VALUE:
            return self.value
        elif offset == TIMER_CTRL:
            return (self.enabled | (self.irq_enable << 1) | (self.periodic << 2))
        elif offset == TIMER_IRQ:
            return 1 if self.irq_pending else 0
        return 0

    def tick(self):
        """Har CPU tsiklida chaqiriladi."""
        if not self.enabled or self.value == 0:
            return None

        self._ticks += 1
        if self._ticks < self.prescaler:
            return None
        self._ticks = 0

        self.value -= 1
        if self.value == 0:
            self._fire_count += 1
            if self.irq_enable:
                self.irq_pending = True
            if self.periodic:
                self.value = self.load_val
            else:
                self.enabled = False
            return IRQ_TIMER
        return None


# ═══════════════════════════════════════════════════════
# GPIO — General Purpose I/O
# ═══════════════════════════════════════════════════════

class GPIO:
    """
    32 ta GPIO pin.
    Kirish/chiqish, IRQ, pull-up/down, alternate function.
    """

    PIN_COUNT = 32

    def __init__(self):
        self.direction   = 0x00000000   # 0=in, 1=out
        self.output_val  = 0x00000000
        self.input_val   = 0x00000000
        self.irq_enable  = 0x00000000
        self.irq_status  = 0x00000000
        self.pull        = 0x00000000
        self.alt_func    = {}
        self._callbacks  = {}   # pin → callback

    def write_reg(self, offset: int, val: int):
        if offset == GPIO_DIR:
            self.direction = val & 0xFFFFFFFF
        elif offset == GPIO_OUT:
            old = self.output_val
            self.output_val = val & 0xFFFFFFFF
            # Callback
            changed = old ^ self.output_val
            for pin in range(32):
                if changed & (1 << pin) and pin in self._callbacks:
                    self._callbacks[pin](bool(val & (1 << pin)))
        elif offset == GPIO_IRQ_EN:
            self.irq_enable = val
        elif offset == GPIO_IRQ_ST:
            self.irq_status &= ~val   # 1 yozsa tozalanadi
        elif offset == GPIO_PULL:
            self.pull = val
        elif offset == GPIO_ALT:
            self.alt_func[val >> 16] = val & 0xFF

    def read_reg(self, offset: int) -> int:
        if offset == GPIO_DIR:    return self.direction
        elif offset == GPIO_OUT:  return self.output_val
        elif offset == GPIO_IN:   return self.input_val
        elif offset == GPIO_IRQ_EN: return self.irq_enable
        elif offset == GPIO_IRQ_ST: return self.irq_status
        elif offset == GPIO_PULL: return self.pull
        return 0

    def set_pin(self, pin: int, val: bool):
        """Tashqaridan pin qiymatini o'rnatish (kirish)."""
        if val:
            self.input_val |= (1 << pin)
        else:
            self.input_val &= ~(1 << pin)
        if self.irq_enable & (1 << pin):
            self.irq_status |= (1 << pin)

    def get_pin(self, pin: int) -> bool:
        return bool(self.output_val & (1 << pin))

    def register_callback(self, pin: int, cb):
        self._callbacks[pin] = cb

    def tick(self):
        if self.irq_status & self.irq_enable:
            return IRQ_GPIO
        return None


# ═══════════════════════════════════════════════════════
# DISPLAY — Framebuffer Display
# ═══════════════════════════════════════════════════════

class Display:
    """
    Virtual framebuffer display.
    320x240, 16-bit color (RGB565).
    """

    WIDTH  = 320
    HEIGHT = 240
    BPP    = 16   # bits per pixel

    def __init__(self):
        self.width   = self.WIDTH
        self.height  = self.HEIGHT
        self.bpp     = self.BPP
        self.enabled = False
        self.fb_addr = 0
        self.fb      = bytearray(self.WIDTH * self.HEIGHT * 2)
        self._dirty  = False
        self._frame_count = 0

    def write_reg(self, offset: int, val: int):
        if offset == DISPLAY_W:    self.width  = val & 0xFFFF
        elif offset == DISPLAY_H:  self.height = val & 0xFFFF
        elif offset == DISPLAY_BPP:self.bpp    = val & 0xFF
        elif offset == DISPLAY_CTRL:
            self.enabled = bool(val & 1)
            if val & 2:   # Flush bit
                self._frame_count += 1
                self._dirty = False
        elif offset == DISPLAY_FB:
            self.fb_addr = val

    def read_reg(self, offset: int) -> int:
        if offset == DISPLAY_W:    return self.width
        elif offset == DISPLAY_H:  return self.height
        elif offset == DISPLAY_BPP:return self.bpp
        elif offset == DISPLAY_CTRL: return self.enabled
        return 0

    def set_pixel(self, x: int, y: int, color: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 2
            self.fb[idx]   = color & 0xFF
            self.fb[idx+1] = (color >> 8) & 0xFF
            self._dirty = True

    def get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 2
            return self.fb[idx] | (self.fb[idx+1] << 8)
        return 0

    def clear(self, color: int = 0):
        if color == 0:
            self.fb = bytearray(len(self.fb))
        else:
            for i in range(0, len(self.fb), 2):
                self.fb[i]   = color & 0xFF
                self.fb[i+1] = (color >> 8) & 0xFF
        self._dirty = True

    def draw_rect(self, x, y, w, h, color):
        for row in range(y, min(y+h, self.height)):
            for col in range(x, min(x+w, self.width)):
                self.set_pixel(col, row, color)

    def stats(self) -> dict:
        return {
            'size': f"{self.width}x{self.height}",
            'bpp': self.bpp,
            'enabled': self.enabled,
            'frames': self._frame_count,
        }


# ═══════════════════════════════════════════════════════
# RTC — Real Time Clock
# ═══════════════════════════════════════════════════════

class RTC:
    """Real vaqt soati."""

    def __init__(self):
        self._epoch = time.time()

    def read_reg(self, offset: int) -> int:
        t = time.localtime()
        regs = [t.tm_sec, t.tm_min, t.tm_hour, t.tm_mday,
                t.tm_mon, t.tm_year, t.tm_wday, t.tm_yday]
        idx = offset // 4
        return regs[idx] if idx < len(regs) else 0

    def write_reg(self, offset: int, val: int):
        pass   # RTC oddatda faqat o'qiladi


# ═══════════════════════════════════════════════════════
# SPI — SPI Bus
# ═══════════════════════════════════════════════════════

class SPI:
    """Oddiy SPI bus emulyatori."""

    def __init__(self):
        self.enabled  = False
        self.speed    = 1000000
        self.mode     = 0
        self.tx_buf   = deque(maxlen=64)
        self.rx_buf   = deque(maxlen=64)
        self._devices = {}   # cs → device

    def write_reg(self, offset: int, val: int):
        if offset == 0:   # TX
            self.tx_buf.append(val & 0xFF)
            # Loopback (test uchun)
            self.rx_buf.append(val & 0xFF)
        elif offset == 4: self.enabled = bool(val & 1)
        elif offset == 8: self.speed   = val

    def read_reg(self, offset: int) -> int:
        if offset == 0:   # RX
            return self.rx_buf.popleft() if self.rx_buf else 0xFF
        elif offset == 4: return self.enabled
        elif offset == 8: return self.speed
        elif offset == 12:  # Status
            return (1 | (1 if self.rx_buf else 0) << 1)
        return 0


# ═══════════════════════════════════════════════════════
# DMA — Direct Memory Access
# ═══════════════════════════════════════════════════════

class DMA:
    """DMA kontroller."""

    def __init__(self, memory=None):
        self.mem      = memory
        self.src_addr = 0
        self.dst_addr = 0
        self.count    = 0
        self.ctrl     = 0
        self.irq_pending = False
        self._transfers  = 0

    def write_reg(self, offset: int, val: int):
        if   offset == 0: self.src_addr = val
        elif offset == 4: self.dst_addr = val
        elif offset == 8: self.count    = val
        elif offset == 12:
            self.ctrl = val
            if val & 1:   # Start bit
                self._do_transfer()

    def read_reg(self, offset: int) -> int:
        if   offset == 0:  return self.src_addr
        elif offset == 4:  return self.dst_addr
        elif offset == 8:  return self.count
        elif offset == 12: return self.ctrl & ~1   # busy bit cleared
        elif offset == 16: return self._transfers
        return 0

    def _do_transfer(self):
        if not self.mem or self.count == 0:
            return
        try:
            data = self.mem.read_bytes(self.src_addr, self.count)
            self.mem.write_bytes(self.dst_addr, data)
            self._transfers += 1
            self.irq_pending = True
        except Exception:
            pass

    def tick(self):
        if self.irq_pending:
            self.irq_pending = False
            return IRQ_DMA
        return None


# ═══════════════════════════════════════════════════════
# SD Card — Xotira kartasi
# ═══════════════════════════════════════════════════════

class SDCard:
    """Virtual SD karta (64KB)."""

    SIZE = 64 * 1024

    def __init__(self):
        self._data      = bytearray(self.SIZE)
        self._sector_sz = 512
        self._cmd       = 0
        self._arg       = 0
        self._response  = 0
        self._ready     = True

    def write_reg(self, offset: int, val: int):
        if   offset == 0: self._cmd = val
        elif offset == 4: self._arg = val
        elif offset == 8:
            if val & 1:   # Execute
                self._execute_cmd()

    def read_reg(self, offset: int) -> int:
        if   offset == 0: return self._cmd
        elif offset == 4: return self._response
        elif offset == 8: return 1 if self._ready else 0
        return 0

    def _execute_cmd(self):
        if self._cmd == 17:   # READ_SINGLE
            sector = self._arg
            addr   = sector * self._sector_sz
            if addr + self._sector_sz <= self.SIZE:
                self._response = addr
        elif self._cmd == 24:  # WRITE_SINGLE
            self._response = self._arg * self._sector_sz

    def read_sector(self, sector: int) -> bytes:
        addr = sector * self._sector_sz
        return bytes(self._data[addr:addr+self._sector_sz])

    def write_sector(self, sector: int, data: bytes):
        addr = sector * self._sector_sz
        n = min(len(data), self._sector_sz)
        self._data[addr:addr+n] = data[:n]


# ═══════════════════════════════════════════════════════
# PIC — Programmable Interrupt Controller
# ═══════════════════════════════════════════════════════

class PIC:
    """8-kanal interrupt kontroller."""

    def __init__(self):
        self.mask    = 0xFF   # Hammasi bloklangan
        self.pending = 0x00
        self.status  = 0x00

    def raise_irq(self, irq: int):
        if not (self.mask & (1 << irq)):
            self.pending |= (1 << irq)

    def acknowledge(self, irq: int):
        self.pending &= ~(1 << irq)
        self.status  &= ~(1 << irq)

    def write_reg(self, offset: int, val: int):
        if   offset == PIC_MASK: self.mask    = val & 0xFF
        elif offset == PIC_EOI:
            irq = val & 0x7
            self.acknowledge(irq)

    def read_reg(self, offset: int) -> int:
        if   offset == PIC_MASK:    return self.mask
        elif offset == PIC_STATUS:  return self.status
        elif offset == PIC_PENDING: return self.pending
        return 0

    def get_pending_irq(self) -> int:
        """Eng yuqori ustuvorlikdagi kutayotgan IRQ."""
        for i in range(8):
            if self.pending & (1 << i):
                return i
        return -1


# ═══════════════════════════════════════════════════════
# DEVICE BUS — Barcha qurilmalarni birlashtiradi
# ═══════════════════════════════════════════════════════

class DeviceBus:
    """
    MMIO (Memory-Mapped I/O) bus.
    CPU xotiraga yozsa/o'qisa shu yerdan o'tadi.
    """

    def __init__(self, memory=None):
        self.uart    = UART()
        self.timer0  = Timer(0)
        self.timer1  = Timer(1)
        self.gpio    = GPIO()
        self.display = Display()
        self.rtc     = RTC()
        self.spi     = SPI()
        self.dma     = DMA(memory)
        self.sdcard  = SDCard()
        self.pic     = PIC()

        self._tick_count = 0
        self._irq_cb     = None   # CPU IRQ handleri

        # MMIO xaritasi: [base, end, device]
        self._map = [
            (UART_BASE,    UART_BASE+0xFFF,    self.uart),
            (TIMER_BASE,   TIMER_BASE+0xFFF,   self.timer0),
            (TIMER_BASE+0x100, TIMER_BASE+0x1FF, self.timer1),
            (GPIO_BASE,    GPIO_BASE+0xFFF,    self.gpio),
            (DISPLAY_BASE, DISPLAY_BASE+0xFFF, self.display),
            (RTC_BASE,     RTC_BASE+0xFFF,     self.rtc),
            (SPI_BASE,     SPI_BASE+0xFFF,     self.spi),
            (DMA_BASE,     DMA_BASE+0xFFF,     self.dma),
            (SD_BASE,      SD_BASE+0xFFF,      self.sdcard),
            (PIC_BASE,     PIC_BASE+0xFFF,     self.pic),
        ]

    def is_io(self, addr: int) -> bool:
        return addr >= 0xFF000000

    def read32(self, addr: int) -> int:
        dev, offset = self._find(addr)
        if dev:
            return dev.read_reg(offset) & 0xFFFFFFFF
        return 0

    def write32(self, addr: int, val: int):
        dev, offset = self._find(addr)
        if dev:
            dev.write_reg(offset, val)

    def _find(self, addr: int):
        for base, end, dev in self._map:
            if base <= addr <= end:
                return dev, addr - base
        return None, 0

    def tick(self):
        """Har CPU tsiklida chaqiriladi."""
        self._tick_count += 1

        irqs = []

        # UART tick
        irq = self.uart.tick()
        if irq is not None: irqs.append(irq)

        # Timer0 tick
        irq = self.timer0.tick()
        if irq is not None: irqs.append(irq)

        # Timer1 har 10 tsiklda
        if self._tick_count % 10 == 0:
            irq = self.timer1.tick()
            if irq is not None: irqs.append(irq)

        # GPIO tick
        irq = self.gpio.tick()
        if irq is not None: irqs.append(irq)

        # DMA tick
        irq = self.dma.tick()
        if irq is not None: irqs.append(irq)

        # IRQlarni PIC ga uzatish
        for irq in irqs:
            self.pic.raise_irq(irq)

        # CPU ga xabar berish
        if irqs and self._irq_cb:
            self._irq_cb(irqs[0])

    def set_irq_callback(self, cb):
        self._irq_cb = cb

    def summary(self) -> dict:
        return {
            'uart':    {'tx_len': len(self.uart.tx_fifo), 'rx_len': len(self.uart.rx_fifo)},
            'timer0':  {'value': self.timer0.value, 'fires': self.timer0._fire_count},
            'timer1':  {'value': self.timer1.value, 'fires': self.timer1._fire_count},
            'gpio':    {'dir': hex(self.gpio.direction), 'out': hex(self.gpio.output_val)},
            'display': self.display.stats(),
            'pic':     {'pending': bin(self.pic.pending), 'mask': bin(self.pic.mask)},
            'ticks':   self._tick_count,
        }

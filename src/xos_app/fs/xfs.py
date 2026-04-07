"""
xOS v4.1 — xFS Fayl Tizimi
============================
Xotiraga mapped, inode asosidagi fayl tizimi.

Disk tuzilmasi (RAM da 0x00800000 dan):
  ┌─────────────────────────────────────┐
  │ [0x00800000]  Superblock  (512 B)  │
  │ [0x00800200]  Inode table (64 KB)  │
  │ [0x00810200]  Data blocks (rest)   │
  └─────────────────────────────────────┘

Superblock (512 byte):
  magic[4]        = "xFS!"
  version[4]      = 1
  block_size[4]   = 512
  total_blocks[4] = 2048
  free_blocks[4]  = ...
  inode_count[4]  = 256
  root_inode[4]   = 1

Inode (64 byte):
  ino[4]          inode raqami
  type[4]         0=free, 1=file, 2=dir
  size[4]         fayl hajmi (byte)
  created[4]      yaratilgan vaqt (unix)
  modified[4]     o'zgartirilgan vaqt
  blocks[10*4]    data block manzillari (max 10)
  name[12]        fayl nomi (null-terminated)

Directory entry (32 byte):
  name[28]        nom
  ino[4]          inode raqami

Syscall integratsiya:
  #3  open(path_addr, flags) → fd
  #4  close(fd)
  #5  read(fd, buf_addr, len) → n
  #6  write(fd, buf_addr, len) → n
  #7  seek(fd, offset, whence) → pos
  #20 mkdir(path_addr)
  #21 unlink(path_addr)
  #22 stat(path_addr, buf_addr)
  #23 listdir(path_addr, buf_addr)
"""

import struct
import time
import os

# ── xFS konstantalar ──────────────────────────────────
XFS_MAGIC      = b'xFS!'
XFS_VERSION    = 1
BLOCK_SIZE     = 512
TOTAL_BLOCKS   = 4096
INODE_COUNT    = 256
INODE_SIZE     = 64
DIR_ENTRY_SIZE = 32
MAX_NAME_LEN   = 27
MAX_BLOCKS_PER_FILE = 10
MAX_FILE_SIZE  = MAX_BLOCKS_PER_FILE * BLOCK_SIZE  # 5 KB

# xFS RAM manzillari
XFS_BASE       = 0x00800000
SUPERBLOCK_OFF = 0x000
INODE_TABLE_OFF= 0x200         # 512 byte dan keyin
DATA_OFF       = 0x200 + INODE_COUNT * INODE_SIZE  # 0x4200

# Inode turlari
INODE_FREE = 0
INODE_FILE = 1
INODE_DIR  = 2

# open() flaglar
O_RDONLY = 0
O_WRONLY = 1
O_RDWR   = 2
O_CREAT  = 0x40
O_TRUNC  = 0x200
O_APPEND = 0x400

# seek() whence
SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2


class xFSError(Exception):
    pass


class Inode:
    """Fayl metadata."""

    def __init__(self, ino: int = 0):
        self.ino      = ino
        self.type     = INODE_FREE
        self.size     = 0
        self.created  = int(time.time())
        self.modified = int(time.time())
        self.blocks   = [0] * MAX_BLOCKS_PER_FILE
        self.name     = ''

    def to_bytes(self) -> bytes:
        name_bytes = self.name.encode('utf-8')[:MAX_NAME_LEN]
        name_bytes = name_bytes.ljust(MAX_NAME_LEN + 1, b'\x00')
        data = struct.pack('<IIIII',
            self.ino, self.type, self.size,
            self.created, self.modified
        )
        data += struct.pack(f'<{MAX_BLOCKS_PER_FILE}I', *self.blocks)
        data += name_bytes
        # Pad to INODE_SIZE
        data = data[:INODE_SIZE].ljust(INODE_SIZE, b'\x00')
        return data

    @classmethod
    def from_bytes(cls, data: bytes, ino: int) -> 'Inode':
        node = cls(ino)
        node.ino, node.type, node.size, node.created, node.modified = \
            struct.unpack('<IIIII', data[:20])
        node.blocks = list(struct.unpack(f'<{MAX_BLOCKS_PER_FILE}I', data[20:60]))
        name_raw = data[60:60 + MAX_NAME_LEN + 1]
        node.name = name_raw.rstrip(b'\x00').decode('utf-8', errors='replace')
        return node

    def is_free(self): return self.type == INODE_FREE
    def is_file(self): return self.type == INODE_FILE
    def is_dir(self):  return self.type == INODE_DIR


class DirEntry:
    """Katalog yozuvi."""

    def __init__(self, name: str = '', ino: int = 0):
        self.name = name
        self.ino  = ino

    def to_bytes(self) -> bytes:
        name_bytes = self.name.encode('utf-8')[:MAX_NAME_LEN]
        name_bytes = name_bytes.ljust(MAX_NAME_LEN + 1, b'\x00')
        return name_bytes + struct.pack('<I', self.ino)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DirEntry':
        name = data[:MAX_NAME_LEN + 1].rstrip(b'\x00').decode('utf-8', errors='replace')
        ino  = struct.unpack('<I', data[MAX_NAME_LEN + 1:MAX_NAME_LEN + 5])[0]
        return cls(name, ino)


class FileDescriptor:
    """Ochiq fayl deskriptori."""

    def __init__(self, inode: Inode, flags: int):
        self.inode  = inode
        self.flags  = flags
        self.pos    = 0
        self.mode   = flags & 3   # O_RDONLY / O_WRONLY / O_RDWR

    def readable(self): return self.mode in (O_RDONLY, O_RDWR)
    def writable(self): return self.mode in (O_WRONLY, O_RDWR)


class xFS:
    """
    xOS Fayl Tizimi.
    Xotiraga mapped (RAM 0x00800000 da).

    Agar memory=None bo'lsa, Python dict da ishlaydi (test uchun).
    """

    def __init__(self, memory=None):
        self.mem = memory

        # In-memory inode table (tezlik uchun)
        self._inodes = {}    # {ino: Inode}
        self._blocks = {}    # {block_no: bytes}
        self._next_block = 1

        # Ochiq fayllar
        self._open_files = {}  # global (machine level), {fd: FileDescriptor}
        self._next_fd = 3

        # Format qilinganmi?
        self._formatted = False

        # Fayllar xotiraga ham yozish
        self._use_mem = (memory is not None)

    # ── Formatlash ────────────────────────────────────────

    def format(self):
        """Yangi bo'sh xFS yaratish."""
        self._formatted = True   # Avval True - rekursiyadan himoya
        self._inodes.clear()
        self._blocks.clear()
        self._next_block = 1
        self._open_files.clear()
        self._next_fd = 3

        # Root katalog (inode 1)
        root = Inode(1)
        root.type = INODE_DIR
        root.name = '/'
        root.size = 0
        self._inodes[1] = root

        # Standart kataloglar
        self.mkdir('/bin')
        self.mkdir('/home')
        self.mkdir('/tmp')
        self.mkdir('/etc')

        # Boshlang'ich fayllar
        self._create_file('/etc/version', b'xOS v4.0\n')
        self._create_file('/etc/motd',    b'Xush kelibsiz xOS ga!\n')
        self._create_file('/bin/hello',
            b'.section text\n    LOAD X0, #72\n    PUTC X0\n'
            b'    LOAD X0, #105\n    PUTC X0\n    HALT\n')

        self._formatted = True

    # ── Katalog operatsiyalari ────────────────────────────

    def mkdir(self, path: str) -> int:
        """Katalog yaratish. 0 = muvaffaqiyat, -1 = xato."""
        parent_path, name = self._split_path(path)
        parent = self._find_inode(parent_path)
        if not parent or not parent.is_dir():
            return -1
        if self._find_in_dir(parent, name):
            return -1   # Allaqachon bor

        node = self._new_inode(INODE_DIR, name)
        self._add_to_dir(parent, name, node.ino)
        return 0

    def listdir(self, path: str = '/') -> list:
        """Katalog tarkibi. [(nom, ino, tur)] ro'yxati."""
        node = self._find_inode(path)
        if not node or not node.is_dir():
            return []
        entries = self._read_dir(node)
        result = []
        for e in entries:
            child = self._inodes.get(e.ino)
            if child:
                result.append((e.name, e.ino, child.type))
        return result

    def ls(self, path: str = '/') -> str:
        """ls chiqishi."""
        entries = self.listdir(path)
        if not entries:
            return f"  {path}: bo'sh yoki topilmadi"
        lines = [f"  {path}:"]
        for name, ino, ftype in sorted(entries):
            icon = '📁' if ftype == INODE_DIR else '📄'
            node = self._inodes.get(ino)
            size = node.size if node else 0
            lines.append(f"    {icon} {name:<24} {size:>6} byte")
        return '\n'.join(lines)

    def tree(self, path: str = '/', prefix: str = '') -> str:
        """Daraxt ko'rinishida katalog."""
        entries = self.listdir(path)
        lines = []
        for i, (name, ino, ftype) in enumerate(sorted(entries)):
            is_last = (i == len(entries) - 1)
            branch = '└── ' if is_last else '├── '
            icon = '📁 ' if ftype == INODE_DIR else '📄 '
            lines.append(prefix + branch + icon + name)
            if ftype == INODE_DIR:
                child_path = path.rstrip('/') + '/' + name
                child_prefix = prefix + ('    ' if is_last else '│   ')
                lines.append(self.tree(child_path, child_prefix))
        return '\n'.join(l for l in lines if l)

    # ── Fayl operatsiyalari ───────────────────────────────

    def open(self, path: str, flags: int = O_RDONLY) -> int:
        """
        Fayl ochish.
        Qaytaradi: fd (>= 3) yoki -1 (xato).
        """
        if not self._formatted:
            self.format()

        node = self._find_inode(path)

        if node is None:
            # Fayl yo'q
            if flags & O_CREAT:
                parent_path, name = self._split_path(path)
                parent = self._find_inode(parent_path)
                if not parent or not parent.is_dir():
                    return -1
                node = self._new_inode(INODE_FILE, name)
                self._add_to_dir(parent, name, node.ino)
            else:
                return -1

        if not node.is_file():
            return -1

        # Truncate?
        if flags & O_TRUNC:
            node.size = 0
            node.blocks = [0] * MAX_BLOCKS_PER_FILE
            self._inodes[node.ino] = node

        fd_obj = FileDescriptor(node, flags)
        if flags & O_APPEND:
            fd_obj.pos = node.size

        fd = self._next_fd
        self._next_fd += 1
        self._open_files[fd] = fd_obj
        return fd

    def close(self, fd: int) -> int:
        """Fayl yopish. 0 = OK, -1 = xato."""
        if fd not in self._open_files:
            return -1
        # Inode ni saqlash
        fd_obj = self._open_files.pop(fd)
        self._inodes[fd_obj.inode.ino] = fd_obj.inode
        return 0

    def read(self, fd: int, length: int) -> bytes:
        """Fayldan o'qish."""
        fd_obj = self._open_files.get(fd)
        if not fd_obj or not fd_obj.readable():
            return b''

        node = fd_obj.inode
        if fd_obj.pos >= node.size:
            return b''

        # Qancha o'qish mumkin
        to_read = min(length, node.size - fd_obj.pos)
        data = self._read_data(node, fd_obj.pos, to_read)
        fd_obj.pos += len(data)
        return data

    def write(self, fd: int, data: bytes) -> int:
        """Faylga yozish."""
        fd_obj = self._open_files.get(fd)
        if not fd_obj or not fd_obj.writable():
            return -1

        node = fd_obj.inode
        written = self._write_data(node, fd_obj.pos, data)
        fd_obj.pos += written
        node.modified = int(time.time())
        return written

    def seek(self, fd: int, offset: int, whence: int = SEEK_SET) -> int:
        """Fayl pozitsiyasini o'zgartirish."""
        fd_obj = self._open_files.get(fd)
        if not fd_obj:
            return -1

        node = fd_obj.inode
        if whence == SEEK_SET:
            fd_obj.pos = offset
        elif whence == SEEK_CUR:
            fd_obj.pos += offset
        elif whence == SEEK_END:
            fd_obj.pos = node.size + offset

        fd_obj.pos = max(0, min(fd_obj.pos, node.size))
        return fd_obj.pos

    def unlink(self, path: str) -> int:
        """Fayl o'chirish."""
        parent_path, name = self._split_path(path)
        parent = self._find_inode(parent_path)
        if not parent:
            return -1

        node = self._find_in_dir(parent, name)
        if not node or not node.is_file():
            return -1

        # Bloklarni bo'shatish
        for block_no in node.blocks:
            if block_no:
                self._blocks.pop(block_no, None)

        # Katalogdan o'chirish
        self._remove_from_dir(parent, name)
        self._inodes.pop(node.ino, None)
        return 0

    def stat(self, path: str) -> dict:
        """Fayl ma'lumotlari."""
        node = self._find_inode(path)
        if not node:
            return {}
        return {
            'ino':      node.ino,
            'type':     'dir' if node.is_dir() else 'file',
            'size':     node.size,
            'name':     node.name,
            'created':  node.created,
            'modified': node.modified,
        }

    def read_file(self, path: str) -> bytes:
        """Qulay: faylni to'liq o'qish."""
        fd = self.open(path, O_RDONLY)
        if fd < 0:
            return b''
        node = self._open_files[fd].inode
        data = self.read(fd, node.size)
        self.close(fd)
        return data

    def write_file(self, path: str, data: bytes) -> int:
        """Qulay: faylga to'liq yozish."""
        fd = self.open(path, O_WRONLY | O_CREAT | O_TRUNC)
        if fd < 0:
            return -1
        n = self.write(fd, data)
        self.close(fd)
        return n

    # ── Xotira bilan integratsiya ─────────────────────────

    def read_from_mem(self, memory, addr: int, length: int) -> bytes:
        """CPU xotirasidan ma'lumot o'qish."""
        try:
            return memory.read_bytes(addr, length)
        except Exception:
            return b''

    def write_to_mem(self, memory, addr: int, data: bytes):
        """CPU xotirasiga ma'lumot yozish."""
        try:
            memory.write_bytes(addr, data)
        except Exception:
            pass

    def read_str_from_mem(self, memory, addr: int) -> str:
        """CPU xotirasidan null-terminated string o'qish."""
        try:
            return memory.read_str(addr)
        except Exception:
            return ''

    # ── Ichki yordamchilar ────────────────────────────────

    def _create_file(self, path: str, content: bytes):
        """Ichki: fayl yaratish va yozish."""
        parent_path, name = self._split_path(path)
        parent = self._find_inode(parent_path)
        if not parent:
            return
        node = self._new_inode(INODE_FILE, name)
        self._add_to_dir(parent, name, node.ino)
        self._write_data(node, 0, content)

    def _new_inode(self, itype: int, name: str) -> Inode:
        """Yangi inode ajratish."""
        # Bo'sh inode topish
        for ino in range(2, INODE_COUNT + 1):
            if ino not in self._inodes:
                node = Inode(ino)
                node.type = itype
                node.name = name[:MAX_NAME_LEN]
                node.created = node.modified = int(time.time())
                self._inodes[ino] = node
                return node
        raise xFSError("Inodlar tugadi!")

    def _alloc_block(self) -> int:
        """Yangi data block ajratish."""
        block_no = self._next_block
        self._next_block += 1
        if self._next_block > TOTAL_BLOCKS:
            raise xFSError("Disk to'ldi!")
        self._blocks[block_no] = bytearray(BLOCK_SIZE)
        return block_no

    def _read_data(self, node: Inode, offset: int, length: int) -> bytes:
        """Inode dan ma'lumot o'qish."""
        result = bytearray()
        block_idx = offset // BLOCK_SIZE
        block_off = offset % BLOCK_SIZE
        remaining = length

        while remaining > 0 and block_idx < MAX_BLOCKS_PER_FILE:
            block_no = node.blocks[block_idx]
            if not block_no:
                break
            block = self._blocks.get(block_no, bytes(BLOCK_SIZE))
            chunk = block[block_off: block_off + remaining]
            result += chunk
            remaining -= len(chunk)
            block_idx += 1
            block_off = 0

        return bytes(result)

    def _write_data(self, node: Inode, offset: int, data: bytes) -> int:
        """Inode ga ma'lumot yozish."""
        written = 0
        block_idx = offset // BLOCK_SIZE
        block_off = offset % BLOCK_SIZE
        remaining = data

        while remaining and block_idx < MAX_BLOCKS_PER_FILE:
            # Block yo'q bo'lsa, yangi ajrat
            if not node.blocks[block_idx]:
                node.blocks[block_idx] = self._alloc_block()

            block_no = node.blocks[block_idx]
            block = bytearray(self._blocks.get(block_no, bytes(BLOCK_SIZE)))

            chunk = remaining[:BLOCK_SIZE - block_off]
            block[block_off:block_off + len(chunk)] = chunk
            self._blocks[block_no] = bytes(block)

            written   += len(chunk)
            remaining  = remaining[len(chunk):]
            block_idx += 1
            block_off  = 0

        node.size = max(node.size, offset + written)
        return written

    def _read_dir(self, node: Inode) -> list:
        """Katalog yozuvlarini o'qish."""
        data = self._read_data(node, 0, node.size)
        entries = []
        for i in range(0, len(data) - DIR_ENTRY_SIZE + 1, DIR_ENTRY_SIZE):
            chunk = data[i:i + DIR_ENTRY_SIZE]
            if len(chunk) < DIR_ENTRY_SIZE:
                break
            e = DirEntry.from_bytes(chunk)
            if e.ino and e.name:
                entries.append(e)
        return entries

    def _add_to_dir(self, dir_node: Inode, name: str, ino: int):
        """Katalogga yozuv qo'shish."""
        e = DirEntry(name, ino)
        self._write_data(dir_node, dir_node.size, e.to_bytes())

    def _remove_from_dir(self, dir_node: Inode, name: str):
        """Katalogdan yozuv o'chirish."""
        data = bytearray(self._read_data(dir_node, 0, dir_node.size))
        new_data = bytearray()
        for i in range(0, len(data) - DIR_ENTRY_SIZE + 1, DIR_ENTRY_SIZE):
            chunk = data[i:i + DIR_ENTRY_SIZE]
            e = DirEntry.from_bytes(bytes(chunk))
            if e.name != name:
                new_data += chunk
        # Dir ni qayta yozish
        dir_node.size = 0
        dir_node.blocks = [0] * MAX_BLOCKS_PER_FILE
        if new_data:
            self._write_data(dir_node, 0, bytes(new_data))

    def _find_in_dir(self, dir_node: Inode, name: str):
        """Katalogda nom bo'yicha inode topish."""
        entries = self._read_dir(dir_node)
        for e in entries:
            if e.name == name:
                return self._inodes.get(e.ino)
        return None

    def _find_inode(self, path: str):
        """Yo'l bo'yicha inode topish."""
        if not self._formatted and path != '/':
            self.format()

        path = path.rstrip('/')
        if not path or path == '/':
            return self._inodes.get(1)   # Root inode

        parts = path.lstrip('/').split('/')
        node = self._inodes.get(1)       # Root dan boshla

        for part in parts:
            if not node or not node.is_dir():
                return None
            node = self._find_in_dir(node, part)

        return node

    def _split_path(self, path: str):
        """'/a/b/c' → ('/a/b', 'c')"""
        path = path.rstrip('/')
        if '/' not in path:
            return '/', path
        idx = path.rfind('/')
        parent = path[:idx] or '/'
        name   = path[idx + 1:]
        return parent, name

    # ── Syscall integratsiya ──────────────────────────────

    def handle_syscall(self, num: int, cpu, memory) -> int:
        """
        CPU SYSCALL instruksiyasidan chaqiriladi.
        X0, X1, X2 = argumentlar.
        Qaytaradi: X0 ga yoziladigan qiymat.
        """
        x0 = cpu.regs[0]
        x1 = cpu.regs[1]
        x2 = cpu.regs[2]

        if num == 3:   # open(path_addr, flags)
            path = self.read_str_from_mem(memory, x0)
            return self.open(path, x1)

        elif num == 4:  # close(fd)
            return self.close(x0)

        elif num == 5:  # read(fd, buf_addr, len)
            data = self.read(x0, x2)
            if data:
                self.write_to_mem(memory, x1, data)
            return len(data)

        elif num == 6:  # write(fd, buf_addr, len)
            data = self.read_from_mem(memory, x1, x2)
            return self.write(x0, data)

        elif num == 7:  # seek(fd, offset, whence)
            return self.seek(x0, x1, x2)

        elif num == 20:  # mkdir(path_addr)
            path = self.read_str_from_mem(memory, x0)
            return self.mkdir(path)

        elif num == 21:  # unlink(path_addr)
            path = self.read_str_from_mem(memory, x0)
            return self.unlink(path)

        elif num == 22:  # stat(path_addr, buf_addr)
            path = self.read_str_from_mem(memory, x0)
            info = self.stat(path)
            if info and x1:
                # size ni X1 manziliga yoz
                size_bytes = struct.pack('<I', info.get('size', 0))
                self.write_to_mem(memory, x1, size_bytes)
            return 0 if info else -1

        return -1

    def status(self) -> str:
        """xFS holati."""
        if not self._formatted:
            return "xFS: formatlanmagan"
        total = len(self._inodes)
        files = sum(1 for n in self._inodes.values() if n.is_file())
        dirs  = sum(1 for n in self._inodes.values() if n.is_dir())
        used_blocks = len(self._blocks)
        return (
            f"xFS v1.0 | "
            f"Inodlar: {total} ({files} fayl, {dirs} katalog) | "
            f"Bloklar: {used_blocks}/{TOTAL_BLOCKS} | "
            f"Hajm: {used_blocks * BLOCK_SIZE // 1024} KB"
        )

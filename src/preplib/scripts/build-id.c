// gcc -nostdlib -static -o print-build-id print-build-id.c
typedef unsigned long long uint64_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;
typedef unsigned long size_t;

#define SYS_read 0
#define SYS_write 1
#define SYS_open 2
#define SYS_close 3
#define SYS_exit 60
#define SYS_lseek 8

#define O_RDONLY 0

#define SEEK_SET 0

// syscall wrapper
static inline long syscall(long n, long a1, long a2, long a3) {
    long ret;
    __asm__ volatile (
        "syscall"
        : "=a" (ret)
        : "a" (n),
          "D" (a1),
          "S" (a2),
          "d" (a3)
        : "rcx", "r11", "memory"
    );
    return ret;
}

static void exit_(int code) {
    syscall(SYS_exit, code, 0, 0);
    __builtin_unreachable();
}

static long open_(const char *path) {
    return syscall(SYS_open, (long)path, O_RDONLY, 0);
}

static long read_(int fd, void *buf, size_t count) {
    return syscall(SYS_read, fd, (long)buf, count);
}

static long write_(int fd, const void *buf, size_t count) {
    return syscall(SYS_write, fd, (long)buf, count);
}

static void close_(int fd) {
    syscall(SYS_close, fd, 0, 0);
}

static long lseek_(int fd, long offset, int whence) {
    return syscall(SYS_lseek, fd, offset, whence);
}

// ELF structures
struct Elf64_Ehdr {
    unsigned char e_ident[16];
    uint16_t e_type;
    uint16_t e_machine;
    uint32_t e_version;
    uint64_t e_entry;
    uint64_t e_phoff;
    uint64_t e_shoff;
    uint32_t e_flags;
    uint16_t e_ehsize;
    uint16_t e_phentsize;
    uint16_t e_phnum;
    uint16_t e_shentsize;
    uint16_t e_shnum;
    uint16_t e_shstrndx;
};

struct Elf64_Shdr {
    uint32_t sh_name;
    uint32_t sh_type;
    uint64_t sh_flags;
    uint64_t sh_addr;
    uint64_t sh_offset;
    uint64_t sh_size;
    uint32_t sh_link;
    uint32_t sh_info;
    uint64_t sh_addralign;
    uint64_t sh_entsize;
};

struct Elf32_Ehdr {
    unsigned char e_ident[16];
    uint16_t e_type;
    uint16_t e_machine;
    uint32_t e_version;
    uint32_t e_entry;
    uint32_t e_phoff;
    uint32_t e_shoff;
    uint32_t e_flags;
    uint16_t e_ehsize;
    uint16_t e_phentsize;
    uint16_t e_phnum;
    uint16_t e_shentsize;
    uint16_t e_shnum;
    uint16_t e_shstrndx;
};

struct Elf32_Shdr {
    uint32_t sh_name;
    uint32_t sh_type;
    uint32_t sh_flags;
    uint32_t sh_addr;
    uint32_t sh_offset;
    uint32_t sh_size;
    uint32_t sh_link;
    uint32_t sh_info;
    uint32_t sh_addralign;
    uint32_t sh_entsize;
};

struct Elf_Nhdr {
    uint32_t n_namesz;
    uint32_t n_descsz;
    uint32_t n_type;
};

#define SHT_NOTE 7
#define EI_CLASS 4
#define ELFCLASS32 1
#define ELFCLASS64 2

static const char hex_table[] = "0123456789abcdef";

static void print_hex(const uint8_t *buf, size_t len) {
    char out[2];
    for (size_t i = 0; i < len; i++) {
        out[0] = hex_table[buf[i] >> 4];
        out[1] = hex_table[buf[i] & 0xf];
        write_(1, out, 2);
    }
}

void _start() {
    long *rbp;
    __asm__ volatile("mov %%rbp, %0" : "=r"(rbp));
    long argc = rbp[1];
    char **argv = (char **)(&rbp[2]);

    if (argc <= 1) {
        exit_(1);
    }

    for (long i = 1; i < argc; i++) {
        const char *filename = argv[i];
        int fd = open_(filename);
        if (fd < 0) continue;

        uint8_t ehdr_buf[64];
        if (read_(fd, ehdr_buf, sizeof(ehdr_buf)) != sizeof(ehdr_buf)) {
            close_(fd);
            continue;
        }

        uint8_t elf_class = ehdr_buf[EI_CLASS];
        if (elf_class == ELFCLASS64) {
            struct Elf64_Ehdr *ehdr = (struct Elf64_Ehdr *)ehdr_buf;
            uint64_t shoff = ehdr->e_shoff;
            uint16_t shentsize = ehdr->e_shentsize;
            uint16_t shnum = ehdr->e_shnum;

            for (uint16_t j = 0; j < shnum; j++) {
                struct Elf64_Shdr shdr;
                if (lseek_(fd, shoff + (uint64_t)j * shentsize, SEEK_SET) < 0) break;
                if (read_(fd, &shdr, sizeof(shdr)) != sizeof(shdr)) break;
                if (shdr.sh_type != SHT_NOTE) continue;

                if (lseek_(fd, shdr.sh_offset, SEEK_SET) < 0) break;
                uint8_t note_buf[512];
                if (read_(fd, note_buf, sizeof(note_buf)) <= 0) break;

                size_t offset = 0;
                while (offset + sizeof(struct Elf_Nhdr) <= shdr.sh_size) {
                    struct Elf_Nhdr *nhdr = (struct Elf_Nhdr *)(note_buf + offset);
                    offset += sizeof(struct Elf_Nhdr);

                    const char *name = (char *)(note_buf + offset);
                    offset += (nhdr->n_namesz + 3) & ~3;

                    uint8_t *desc = (uint8_t *)(note_buf + offset);
                    offset += (nhdr->n_descsz + 3) & ~3;

                    if (nhdr->n_type == 3 && nhdr->n_namesz == 4 && name[0] == 'G' && name[1] == 'N' && name[2] == 'U') {
                        print_hex(desc, nhdr->n_descsz);
                        write_(1, " ", 1);
                        size_t len = 0;
                        while (filename[len]) len++;
                        write_(1, filename, len);
                        write_(1, "\n", 1);
                        break;
                    }
                }
            }
        } else if (elf_class == ELFCLASS32) {
            struct Elf32_Ehdr *ehdr = (struct Elf32_Ehdr *)ehdr_buf;
            uint32_t shoff = ehdr->e_shoff;
            uint16_t shentsize = ehdr->e_shentsize;
            uint16_t shnum = ehdr->e_shnum;

            for (uint16_t j = 0; j < shnum; j++) {
                struct Elf32_Shdr shdr;
                if (lseek_(fd, shoff + (uint32_t)j * shentsize, SEEK_SET) < 0) break;
                if (read_(fd, &shdr, sizeof(shdr)) != sizeof(shdr)) break;
                if (shdr.sh_type != SHT_NOTE) continue;

                if (lseek_(fd, shdr.sh_offset, SEEK_SET) < 0) break;
                uint8_t note_buf[512];
                if (read_(fd, note_buf, sizeof(note_buf)) <= 0) break;

                size_t offset = 0;
                while (offset + sizeof(struct Elf_Nhdr) <= shdr.sh_size) {
                    struct Elf_Nhdr *nhdr = (struct Elf_Nhdr *)(note_buf + offset);
                    offset += sizeof(struct Elf_Nhdr);

                    const char *name = (char *)(note_buf + offset);
                    offset += (nhdr->n_namesz + 3) & ~3;

                    uint8_t *desc = (uint8_t *)(note_buf + offset);
                    offset += (nhdr->n_descsz + 3) & ~3;

                    if (nhdr->n_type == 3 && nhdr->n_namesz == 4 && name[0] == 'G' && name[1] == 'N' && name[2] == 'U') {
                        print_hex(desc, nhdr->n_descsz);
                        write_(1, " ", 1);
                        size_t len = 0;
                        while (filename[len]) len++;
                        write_(1, filename, len);
                        write_(1, "\n", 1);
                        break;
                    }
                }
            }
        }

        close_(fd);
    }

    exit_(0);
}

#include "rott64_flash_save.h"
#include <flashram.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MAGIC 0x52363453u
#define VERSION 1u
#define FLASH_SIZE 0x20000u
#define HEADER_SIZE 32u
#define PAYLOAD_MAX (FLASH_SIZE-HEADER_SIZE)
#define RAW_MAX (384u*1024u)
#define HWRITE 0x6401
#define HAPPEND 0x6402
#define HREAD 0x6403
#define FLAG_RAW 1u

typedef struct {
    uint32_t magic,version,sequence,flags,raw_size,stored_size,payload_crc,header_crc;
} save_header_t;

static uint8_t *raw;
static size_t raw_size,cap,pos;
static int current,initialized,available,loaded,transaction_active,committed_ready;

static uint32_t crc32(const void *p,size_t n){
    const uint8_t *b=p; uint32_t c=0xffffffffu;
    while(n--){ unsigned k; c^=*b++; for(k=0;k<8;k++) c=(c>>1)^(0xedb88320u&(0u-(c&1u))); }
    return ~c;
}
static int reserve(size_t n){
    uint8_t *q; size_t c=cap?cap:65536u;
    if(n>RAW_MAX){errno=EFBIG;return 0;} while(c<n)c*=2u;
    if (c == cap) return 1;
    q = realloc(raw, c);
    if (!q) { errno = ENOMEM; return 0; }
    raw=q;cap=c;return 1;
}
static size_t pack(const uint8_t*s,size_t n,uint8_t*d,size_t m){
    size_t i=0,o=0;
    while(i<n){
        size_t r=1;
        while(i+r<n&&r<128&&s[i+r]==s[i])r++;
        if(r>=3){
            if (o + 2 > m) return 0;
            d[o++] = (uint8_t)(257 - r);
            d[o++] = s[i];
            i += r;
        }else{
            size_t st=i,l=0;
            while(i<n&&l<128){
                r=1;while(i+r<n&&r<128&&s[i+r]==s[i])r++;
                if (r >= 3) break;
                i++;
                l++;
            }
            if(!l)continue;
            if (o + 1 + l > m) return 0;
            d[o++] = (uint8_t)(l - 1);
            memcpy(d + o, s + st, l);
            o += l;
        }
    }
    return o;
}
static int unpack(const uint8_t*s,size_t n,uint8_t*d,size_t m){
    size_t i=0,o=0;
    while(i<n){
        uint8_t t=s[i++];
        if(t<=127){
            size_t c=(size_t)t+1;if(i+c>n||o+c>m)return 0;memcpy(d+o,s+i,c);i+=c;o+=c;
        }else if(t>=129){
            size_t c=257u-(size_t)t;if(i>=n||o+c>m)return 0;memset(d+o,s[i++],c);o+=c;
        }
    }
    return o==m;
}
static void init(void){
    if (initialized) return;
    initialized = 1;
    flashram_init();
    available = flashram_detect() >= (int)FLASH_SIZE;
}
static int load_committed(void){
    save_header_t h; uint8_t *s; uint32_t hc;
    if (committed_ready && raw_size != 0) return 1;
    if (loaded) return 0;
    loaded = 1;
    init();
    if (!available) return 0;
    if(flashram_read(&h,0,sizeof(h))!=(int)sizeof(h))return 0;
    if(h.magic!=MAGIC||h.version!=VERSION||!h.raw_size||h.raw_size>RAW_MAX||
       !h.stored_size||h.stored_size>PAYLOAD_MAX)return 0;
    hc=h.header_crc;h.header_crc=0;if(crc32(&h,sizeof(h))!=hc)return 0;
    s=malloc(h.stored_size);if(!s)return 0;
    if(flashram_read(s,HEADER_SIZE,h.stored_size)!=(int)h.stored_size||
       crc32(s,h.stored_size)!=h.payload_crc){free(s);return 0;}
    if(!reserve(h.raw_size)){free(s);return 0;}
    if(h.flags&FLAG_RAW){
        if(h.stored_size!=h.raw_size){free(s);return 0;}memcpy(raw,s,h.raw_size);
    }else if(!unpack(s,h.stored_size,raw,h.raw_size)){free(s);return 0;}
    free(s);raw_size=h.raw_size;committed_ready=1;return 1;
}
static int commit(void){
    save_header_t h,old;uint8_t *s;size_t z;uint32_t seq=0;
    init();if(!available||!raw_size){errno=ENODEV;return 0;}
    s=malloc(PAYLOAD_MAX);if(!s){errno=ENOMEM;return 0;}
    z=pack(raw,raw_size,s,PAYLOAD_MAX);
    memset(&h,0,sizeof(h));h.magic=MAGIC;h.version=VERSION;
    if(flashram_read(&old,0,sizeof(old))==(int)sizeof(old)&&old.magic==MAGIC)seq=old.sequence;
    h.sequence=seq+1;h.raw_size=(uint32_t)raw_size;
    if(!z||z>=raw_size){
        if(raw_size>PAYLOAD_MAX){free(s);errno=EFBIG;return 0;}
        memcpy(s,raw,raw_size);z=raw_size;h.flags=FLAG_RAW;
    }
    h.stored_size=(uint32_t)z;h.payload_crc=crc32(s,z);h.header_crc=0;h.header_crc=crc32(&h,sizeof(h));
    if(flashram_write(s,HEADER_SIZE,z)!=(int)z||flashram_write(&h,0,sizeof(h))!=(int)sizeof(h)){
        free(s);errno=EIO;return 0;
    }
    free(s);loaded=1;committed_ready=1;transaction_active=0;return 1;
}
static int native(const char*p){
    const char*n;if(!p)return 0;n=strrchr(p,'/');n=n?n+1:p;return strcmp(n,"rottgam0.rot")==0;
}
int rott64_save_open_write(const char*p){
    if(!native(p)){errno=EROFS;return-1;}
    if(!reserve(65536))return-1;
    raw_size=pos=0;current=HWRITE;transaction_active=1;return current;
}
int rott64_save_open_append(const char*p){
    if(!native(p)||!transaction_active){errno=EBADF;return-1;}
    pos=raw_size;current=HAPPEND;return current;
}
int rott64_save_open_read(const char*p){
    if(!native(p)){errno=ENOENT;return-1;}
    /* SaveTheGame reopens its in-progress image to calculate Taradino's
       inner checksum. Only that transaction may read uncommitted staging. */
    if(!(transaction_active&&raw_size!=0)&&!load_committed()){
        errno=ENOENT;return-1;
    }
    pos=0;current=HREAD;return current;
}
void rott64_save_write(int h,const void*s,int n){size_t z;if((h!=HWRITE&&h!=HAPPEND)||!s||n<0){errno=EBADF;return;}z=(size_t)n;if(!reserve(pos+z))return;memcpy(raw+pos,s,z);pos+=z;if(pos>raw_size)raw_size=pos;}
void rott64_save_read(int h,void*d,int n){size_t z;if(h!=HREAD||!d||n<0){errno=EBADF;return;}z=(size_t)n;if(pos+z>raw_size){errno=EIO;return;}memcpy(d,raw+pos,z);pos+=z;}
int rott64_save_close(int h){int ok=1;if(h==HAPPEND)ok=commit();if(h!=current&&h!=HREAD){errno=EBADF;return-1;}current=0;return ok?0:-1;}
int rott64_save_filelength(int h){if(h!=HREAD){errno=EBADF;return-1;}return(int)raw_size;}
int rott64_save_load_file(const char*p,void**b){
    void*q;
    /* Menu/header and game-load callers must never see an incomplete staging
       buffer. Only a CRC-validated committed FlashRAM image is loadable. */
    if(!b||!native(p)||!load_committed()){errno=ENOENT;return-1;}
    q=malloc(raw_size);if(!q){errno=ENOMEM;return-1;}
    memcpy(q,raw,raw_size);*b=q;return(int)raw_size;
}
char *rott64_save_case_exists(const char*p){
    char*q;
    /* Slot scanning must only advertise a fully committed, validated save. */
    if(!native(p)||!load_committed())return NULL;
    q=malloc(strlen(p)+1);if(q)strcpy(q,p);return q;
}
int rott64_save_unlink(const char*p){
    save_header_t h;if(!native(p)){errno=EROFS;return-1;}init();
    if(!available){errno=ENODEV;return-1;}memset(&h,0xff,sizeof(h));
    raw_size=0;loaded=1;committed_ready=0;transaction_active=0;
    return flashram_write(&h,0,sizeof(h))==(int)sizeof(h)?0:-1;
}

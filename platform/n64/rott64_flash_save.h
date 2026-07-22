#ifndef ROTT64_FLASH_SAVE_H
#define ROTT64_FLASH_SAVE_H
int rott64_save_open_write(const char*);
int rott64_save_open_append(const char*);
int rott64_save_open_read(const char*);
void rott64_save_write(int,const void*,int);
void rott64_save_read(int,void*,int);
int rott64_save_close(int);
int rott64_save_filelength(int);
int rott64_save_load_file(const char*,void**);
char *rott64_save_case_exists(const char*);
int rott64_save_unlink(const char*);
#endif

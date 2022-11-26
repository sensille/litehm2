#ifndef __FLASH_H__
#define __FLASH_H__

#define FLASH_ERASE_SIZE 4096 /* must be power of 2 */
#define FLASH_PAGE_SIZE 256 /* ditto */

void flash_init(void);
void flash_read_uuid(uint8_t *uuid);
void flash_read_id(uint8_t *id);
void flash_write_page(uint32_t addr, const uint8_t *data, int len);
void flash_read_page(uint32_t addr, uint8_t *data, int len);
void flash_erase_sector(uint32_t addr);
void flash_erase_block64(uint32_t addr);

#endif

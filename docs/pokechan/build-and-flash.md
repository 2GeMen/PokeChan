# 编译与刷机

## 准备

- 硬件：M5Stack StackChan（CoreS3 主控：ESP32-S3，16 MB Flash，8 MB PSRAM），USB-C 数据线。
- 工具链：[ESP-IDF v5.5.4](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32s3/index.html)。
- **仓库要放在不含空格的路径下**。ESP-IDF 的链接器不支持带空格的路径，会报 `cannot find …lib/esp32s3`。

## 先备份（强烈建议）

刷机前把整片 Flash 读出来保存。出了问题可以整片写回，Wi-Fi 设置、小智激活信息和素材分区都会恢复原样：

```bash
esptool --chip esp32s3 --port /dev/cu.usbmodem101 -b 921600 read-flash 0 0x1000000 stackchan_full_16MB.bin
```

恢复：

```bash
esptool --chip esp32s3 --port /dev/cu.usbmodem101 -b 921600 write-flash 0 stackchan_full_16MB.bin
```

备份文件里的 NVS 存着你的 Wi-Fi 密码，不要分享出去。

## 编译

```bash
cd firmware
python3 ./fetch_repos.py        # 拉取依赖，并给 xiaozhi-esp32 打上 patches/xiaozhi-esp32.patch
idf.py build
```

第一次编译会通过组件管理器下载 `managed_components/`。之后新增源文件时，要先执行一次 `idf.py reconfigure`，因为 `main/CMakeLists.txt` 是用 GLOB 收集源文件的。

## 刷机

**只刷 app 分区**（0x20000），这样 NVS（Wi-Fi、小智激活信息、Muse 令牌、当前选择的脸）和 assets 分区都保持不变：

```bash
idf.py app-flash
# 或者
esptool --chip esp32s3 --port /dev/cu.usbmodem101 -b 921600 write-flash 0x20000 build/stack-chan.bin
```

`idf.py flash` 会把 bootloader、分区表和 app 一起刷进去。全新的设备可以这样刷；已经在用的设备建议用 `app-flash`。

分区布局（沿用 StackChan 原版）：

| 分区 | 偏移 | 大小 | 内容 |
| --- | --- | --- | --- |
| nvs | 0x9000 | 16 KB | Wi-Fi、小智、`muse_hatch`、`avatar` 设置 |
| otadata | 0xd000 | 8 KB | OTA 状态 |
| ota_0 | 0x20000 | 0x4f0000 | 固件（PokeChan 编出来约 4.2 MB，还剩约 16%） |
| ota_1 | 0x510000 | 0x4f0000 | OTA 备用 |
| assets | 0xa00000 | 4 MB | 唤醒词模型、字体、表情等 |
| coredump | 0xe00000 | | 崩溃转储 |

## 首次启动

1. 开机后按 StackChan 原有流程配网，并在 [xiaozhi.me](https://xiaozhi.me) 激活设备（PokeChan 没有改动这一步）。
2. 说 "Hi Stack-chan" 唤醒，然后试试"换成皮卡丘"。
3. 想用 Muse 的话，接着看 [muse.md](muse.md)；想用 Mac 端的天气和搜索，看 [mcp-server.md](mcp-server.md)。

## 内存说明

在 StackChan 上同时跑小智、Muse 和宝可梦皮肤，内部 SRAM 比较紧张。PokeChan 做了以下处理：

- Muse 会话的大缓冲区（约 10 KB）、串口行缓冲区和 Muse 问答任务的栈都放在 PSRAM（`CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY=y`）。
- Muse 在开机 25 秒后才开始连接，避免和唤醒词、音频任务抢开机时的内存。
- 皮肤图片在切换时才从 PNG 解码到 PSRAM，每个角色约 0.5 到 1 MB；切换之后旧皮肤的图片会释放掉。

实测：对话过程中空闲的内部 SRAM 约 25 KB（最低约 20 KB），待机时约 40 KB，唤醒词正常，没有出现 `AFE Ringbuffer full`。

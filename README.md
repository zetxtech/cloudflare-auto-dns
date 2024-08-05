# Cloudflare Auto DNS

## 简介

Cloudflare Auto DNS 是一个自动化 DNS 管理工具，根据网页是否可以正常访问，动态更新 Cloudflare 的 DNS 记录为备用记录。支持 Web / Ping / TCP 方式进行检查，且支持 Docker 部署。

## 安装与部署

### 准备

需要预先进行以下配置:

1. 在 Cloudflare 右上角 -> 个人资料 -> API 令牌, 生成一个新的 API 令牌, 使用 DNS 编辑模板 (即开通所需域名的 区域.DNS 权限), 之后填入配置文件中.
2. 为需要自动调整的域名创建一个任意 A/AAAA/CNAME 条目 (切换时无法新建条目).

### Docker 部署

首先克隆仓库:

```sh
git clone https://github.com/zetxtech/cloudflare-auto-dns.git
cd cloudflare-auto-dns
```

将 `config.example.yml` 重命名为 `config.yml` 并根据文件内注释修改. 然后运行以下命令：

```sh
docker build . -t cloudflare-auto-dns
docker run -d -v $(pwd)/config.yml:/app/config.yml cloudflare-auto-dns
```

## Docker Compose 部署

首先克隆仓库:

```sh
mkdir cloudflare-auto-dns
cd cloudflare-auto-dns
git clone https://github.com/zetxtech/cloudflare-auto-dns.git src
mkdir data
cp src/config.example.yml data/config.yml
```

在 `cloudflare-auto-dns` 目录下创建 `docker-compose.yml`：

```yaml
version: '3.9'
services:
  cloudflare-auto-dns:
    build: ./cloudflare-auto-dns/src
    container_name: cloudflare-auto-dns
    restart: unless-stopped
    volumes:
      - ./cloudflare-auto-dns/data:/app
```

然后, 在 `cloudflare-auto-dns` 目录下, 根据文件内注释修改 `data/config.yml`. 然后运行以下命令：

```sh
docker-compose up -d
```

你可以在 `cloudflare-auto-dns` 目录下, 通过以下命令查看日志：

```sh
docker-compose logs -f
```

### 配置文件
配置文件 `config.yml` 的格式如下：

```yml
debug: false
cloudflare:
  token: yourtoken
interval: 60
retries: 3
records:
- domain: yourdomain.com
  subdomain: www
  checks:
    - type: web
      target: https://www.yourdomain.com
      timeout: 10
      status: 200-299,401
    - type: web
      target: https://sub.yourdomain.com
      regex: Success
    - type: ping
      target: www.yourdomain.com
      percentage: 80
    - type: tcping
      timeout: 2
  pool:
    - type: CNAME
      content: yourcdn.com
      proxied: false
```

#### 配置项说明
`cloudflare`:
    `token`: Cloudflare API Token

`debug`: 是否开启调试模式, 不开启时不显示测试成功的日志 (可选, 默认为 `false`)
`interval`: 检查运行间隔时间 (秒) (可选, 默认为 `60`)
`retries`: 几次检查失败后,进行切换 (可选, 默认为 `3`)

`records`: DNS 记录配置列表:
    `domain`: 域名
    `subdomain`: 子域名, 可以包含或不包含域名, 也可以使用 '@'
    `checks`: 检查配置列表, 可以包含三种类型的检查:
        `type`: web / ping / tcping
        `target`: 检查目标地址, 当为 web 检查时使用 URL, ping 和 tcping 时使用域名或 IP (可选, 默认为 `subdomain` 对应域名)
        `status`: web 检查状态码范围, 例如可以为 200-299,401 (可选, 默认为 200-299)
        `regex`: web 检查返回内容中必须包含正则表达式 (可选, 默认为不要求)
        `percentage`: ping 检查 5 次发包丢包率必须低于该比率, 例如 80 表示允许丢 1 包 (可选, 默认为 `80`)
        `port`: tcping 端口 (可选, 默认为 `80`)
        `timeout`: tcping 检查超时时间 (可选, 默认为 `2`)
`pool`: 可切换的 源 DNS 记录列表:
    `type`: DNS 记录类型 (A / AAAA / CNAME)
    `content`: DNS 记录内容
    `proxied`: 是否开启 Cloudflare 代理 (可选, 默认为 `false`)

## 贡献

欢迎提交 Issues 和 Pull Requests 来改进本项目！

## 许可证

本项目使用 MIT 许可证。详细信息请参阅 LICENSE 文件。
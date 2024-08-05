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

接下来, 在 `cloudflare-auto-dns` 目录下运行以下命令：

```sh
docker-compose up -d
```

你可以通过以下命令查看日志：

```sh
docker-compose logs -f
```

## 贡献

欢迎提交 Issues 和 Pull Requests 来改进本项目！

## 许可证

本项目使用 MIT 许可证。详细信息请参阅 LICENSE 文件。
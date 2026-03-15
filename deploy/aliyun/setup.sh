#!/usr/bin/env bash
# ====================================================
# BQT 阿里云 ECS 一键初始化脚本
# 在全新的 ECS 实例上运行，自动安装所有依赖并部署服务
#
# 使用方法:
#   curl -sSL <此脚本URL> | bash
#   或: bash setup.sh
#
# 支持系统: Ubuntu 20.04/22.04, CentOS 7/8, Debian 11/12, Alibaba Cloud Linux
# ====================================================

set -euo pipefail

# ============ 颜色输出 ============
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ============ 前置检查 ============
[[ $EUID -ne 0 ]] && error "请使用 root 用户运行此脚本: sudo bash setup.sh"

PROJECT_DIR="/opt/bqt"
REPO_URL="https://github.com/DMLayMan/binance-quant-trading.git"

info "========================================="
info "  BQT 阿里云一键部署 v1.0"
info "========================================="

# ============ 检测包管理器 ============
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then
        PKG_MGR="apt"
        PKG_UPDATE="apt-get update -y"
        PKG_INSTALL="apt-get install -y"
    elif command -v yum &>/dev/null; then
        PKG_MGR="yum"
        PKG_UPDATE="yum makecache -y"
        PKG_INSTALL="yum install -y"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        PKG_UPDATE="dnf makecache -y"
        PKG_INSTALL="dnf install -y"
    else
        error "不支持的操作系统，请使用 Ubuntu/CentOS/Debian"
    fi
}

# ============ 1. 系统基础依赖 ============
install_base() {
    info "安装基础依赖..."
    detect_pkg_manager
    $PKG_UPDATE
    $PKG_INSTALL curl wget git ca-certificates gnupg lsof
    ok "基础依赖安装完成"
}

# ============ 2. 安装 Docker ============
install_docker() {
    if command -v docker &>/dev/null; then
        ok "Docker 已安装: $(docker --version)"
        return
    fi

    info "安装 Docker..."

    if [[ "$PKG_MGR" == "apt" ]]; then
        # Debian/Ubuntu
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        # 检测发行版
        . /etc/os-release
        if [[ "$ID" == "ubuntu" ]]; then
            REPO_DIST="ubuntu"
        else
            REPO_DIST="debian"
        fi

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/${REPO_DIST} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    else
        # CentOS/RHEL/Alibaba Cloud Linux
        yum install -y yum-utils
        yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    fi

    # 配置阿里云 Docker 镜像加速
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'DAEMON_EOF'
{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DAEMON_EOF

    systemctl enable docker
    systemctl start docker
    ok "Docker 安装完成: $(docker --version)"
}

# ============ 3. 安装 Docker Compose ============
install_compose() {
    if docker compose version &>/dev/null; then
        ok "Docker Compose 已安装: $(docker compose version --short)"
        return
    fi

    info "安装 Docker Compose..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | head -1 | cut -d '"' -f 4)
    COMPOSE_VERSION=${COMPOSE_VERSION:-v2.27.0}

    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ok "Docker Compose 安装完成: $(docker compose version --short)"
}

# ============ 4. 配置防火墙 ============
setup_firewall() {
    info "配置防火墙..."

    if command -v ufw &>/dev/null; then
        ufw allow 22/tcp   # SSH
        ufw allow 80/tcp   # HTTP
        ufw allow 443/tcp  # HTTPS
        ufw --force enable
        ok "UFW 防火墙已配置"
    elif command -v firewall-cmd &>/dev/null; then
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        ok "Firewalld 已配置"
    else
        warn "未检测到防火墙工具，请手动在阿里云安全组中放行 80/443 端口"
    fi
}

# ============ 5. 克隆项目 ============
clone_project() {
    info "部署项目到 ${PROJECT_DIR}..."

    if [[ -d "${PROJECT_DIR}/.git" ]]; then
        info "项目已存在，拉取最新代码..."
        cd "$PROJECT_DIR"
        git pull origin main || git pull origin master || true
    else
        rm -rf "$PROJECT_DIR"
        git clone "$REPO_URL" "$PROJECT_DIR"
    fi

    cd "$PROJECT_DIR"
    ok "项目代码就绪"
}

# ============ 6. 配置环境变量 ============
setup_env() {
    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        warn "未检测到 .env 文件"
        cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"

        echo ""
        echo -e "${YELLOW}============================================${NC}"
        echo -e "${YELLOW}  请编辑 ${PROJECT_DIR}/.env 填入 API 密钥  ${NC}"
        echo -e "${YELLOW}  vim ${PROJECT_DIR}/.env                    ${NC}"
        echo -e "${YELLOW}============================================${NC}"
        echo ""

        read -rp "是否现在编辑 .env 文件？[Y/n] " edit_env
        if [[ "${edit_env:-Y}" =~ ^[Yy]$ ]]; then
            ${EDITOR:-vi} "${PROJECT_DIR}/.env"
        fi
    else
        ok ".env 文件已存在"
    fi
}

# ============ 7. 配置域名（可选） ============
setup_domain() {
    echo ""
    read -rp "是否配置域名和 SSL 证书？[y/N] " use_domain

    if [[ "${use_domain:-N}" =~ ^[Yy]$ ]]; then
        read -rp "请输入域名 (例: bqt.example.com): " DOMAIN
        read -rp "请输入邮箱 (用于 Let's Encrypt): " EMAIL

        if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
            warn "域名或邮箱为空，跳过 SSL 配置"
            return
        fi

        # 替换 Nginx 配置中的域名
        NGINX_CONF="${PROJECT_DIR}/deploy/aliyun/nginx/default.conf"
        sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" "$NGINX_CONF"

        # 启用 HTTPS 重定向
        sed -i 's/# return 301/return 301/' "$NGINX_CONF"

        # 先用 HTTP 启动以便 Certbot 验证
        info "首次启动服务（HTTP 模式）以申请 SSL 证书..."
        cd "${PROJECT_DIR}"
        docker compose -f deploy/aliyun/docker-compose.prod.yml up -d nginx dashboard

        sleep 5

        # 申请证书
        info "申请 Let's Encrypt SSL 证书..."
        docker compose -f deploy/aliyun/docker-compose.prod.yml run --rm certbot \
            certbot certonly --webroot -w /var/www/certbot \
            --email "$EMAIL" \
            --agree-tos --no-eff-email \
            -d "$DOMAIN"

        if [[ $? -eq 0 ]]; then
            # 启用 HTTPS server block
            sed -i 's/^# server {/server {/' "$NGINX_CONF"
            sed -i 's/^#     /    /' "$NGINX_CONF"
            sed -i 's/^# }/}/' "$NGINX_CONF"
            ok "SSL 证书申请成功！"
        else
            warn "SSL 证书申请失败，使用 HTTP 模式继续"
        fi

        # 重启 Nginx 加载证书
        docker compose -f deploy/aliyun/docker-compose.prod.yml restart nginx
    fi
}

# ============ 8. 启动服务 ============
start_services() {
    info "构建并启动所有服务..."
    cd "${PROJECT_DIR}"
    docker compose -f deploy/aliyun/docker-compose.prod.yml up -d --build

    sleep 5

    info "服务状态："
    docker compose -f deploy/aliyun/docker-compose.prod.yml ps

    echo ""
    ok "========================================="
    ok "  部署完成！"
    ok "========================================="
    echo ""

    # 获取公网 IP
    PUBLIC_IP=$(curl -s --connect-timeout 3 http://100.100.100.200/latest/meta-data/eip 2>/dev/null \
        || curl -s --connect-timeout 3 ifconfig.me 2>/dev/null \
        || echo "YOUR_SERVER_IP")

    echo -e "  ${GREEN}Dashboard:${NC}  http://${PUBLIC_IP}"
    echo -e "  ${GREEN}API 文档:${NC}   http://${PUBLIC_IP}/docs"
    echo ""
    echo -e "  ${YELLOW}常用命令:${NC}"
    echo "  查看日志:   cd ${PROJECT_DIR} && docker compose -f deploy/aliyun/docker-compose.prod.yml logs -f"
    echo "  重启服务:   cd ${PROJECT_DIR} && docker compose -f deploy/aliyun/docker-compose.prod.yml restart"
    echo "  停止服务:   cd ${PROJECT_DIR} && docker compose -f deploy/aliyun/docker-compose.prod.yml down"
    echo "  更新部署:   cd ${PROJECT_DIR} && git pull && docker compose -f deploy/aliyun/docker-compose.prod.yml up -d --build"
    echo ""
}

# ============ 9. 配置自动更新 cron ============
setup_cron() {
    read -rp "是否配置每日自动拉取更新？[y/N] " auto_update
    if [[ "${auto_update:-N}" =~ ^[Yy]$ ]]; then
        CRON_CMD="0 4 * * * cd ${PROJECT_DIR} && git pull && docker compose -f deploy/aliyun/docker-compose.prod.yml up -d --build >> /var/log/bqt-update.log 2>&1"
        (crontab -l 2>/dev/null | grep -v "bqt"; echo "$CRON_CMD") | crontab -
        ok "已添加每日 04:00 自动更新任务"
    fi
}

# ============ 主流程 ============
main() {
    install_base
    install_docker
    install_compose
    setup_firewall
    clone_project
    setup_env
    setup_domain
    start_services
    setup_cron

    echo ""
    ok "全部完成！如有问题请查看日志: docker compose -f deploy/aliyun/docker-compose.prod.yml logs -f"
}

main "$@"

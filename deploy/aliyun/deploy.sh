#!/usr/bin/env bash
# ====================================================
# BQT 本地一键部署到阿里云 ECS
#
# 从你的开发机器运行此脚本，自动完成：
#   1. 通过阿里云 CLI 创建 ECS 实例（可选）
#   2. SSH 上传项目代码
#   3. 远程执行 setup.sh 完成部署
#
# 前置条件:
#   - 安装阿里云 CLI: pip install aliyun-cli  或  brew install aliyun-cli
#   - 已配置 aliyun CLI: aliyun configure
#   - 或者已有 ECS 实例的 IP 地址
#
# 使用方法:
#   # 方式 A: 已有 ECS 实例
#   bash deploy.sh --host 47.98.xxx.xxx --user root --key ~/.ssh/id_rsa
#
#   # 方式 B: 自动创建 ECS 实例
#   bash deploy.sh --create-ecs --region cn-hangzhou
# ====================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ============ 默认参数 ============
HOST=""
USER="root"
SSH_KEY=""
SSH_PORT=22
CREATE_ECS=false
REGION="cn-hangzhou"
INSTANCE_TYPE="ecs.t6-c1m2.large"   # 2vCPU 4GB (~¥60/月)
IMAGE_ID="ubuntu_22_04_x64_20G_alibase_20240101.vhd"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# ============ 参数解析 ============
usage() {
    cat <<EOF
用法: bash deploy.sh [选项]

选项:
  --host HOST          ECS 公网 IP
  --user USER          SSH 用户名 (默认: root)
  --key FILE           SSH 私钥路径
  --port PORT          SSH 端口 (默认: 22)
  --create-ecs         自动创建 ECS 实例
  --region REGION      阿里云区域 (默认: cn-hangzhou)
  --instance-type TYPE 实例规格 (默认: ecs.t6-c1m2.large)
  -h, --help           显示帮助

示例:
  # 部署到已有服务器
  bash deploy.sh --host 47.98.1.2 --key ~/.ssh/id_rsa

  # 自动创建 ECS 并部署
  bash deploy.sh --create-ecs --region cn-shanghai
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)         HOST="$2"; shift 2 ;;
        --user)         USER="$2"; shift 2 ;;
        --key)          SSH_KEY="$2"; shift 2 ;;
        --port)         SSH_PORT="$2"; shift 2 ;;
        --create-ecs)   CREATE_ECS=true; shift ;;
        --region)       REGION="$2"; shift 2 ;;
        --instance-type) INSTANCE_TYPE="$2"; shift 2 ;;
        -h|--help)      usage ;;
        *)              error "未知参数: $1\n运行 deploy.sh --help 查看帮助" ;;
    esac
done

# ============ SSH 参数构建 ============
build_ssh_opts() {
    SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -p ${SSH_PORT}"
    if [[ -n "$SSH_KEY" ]]; then
        SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
    fi
    SCP_OPTS="${SSH_OPTS}"
}

# ============ 创建 ECS 实例 ============
create_ecs_instance() {
    info "正在创建阿里云 ECS 实例..."
    command -v aliyun &>/dev/null || error "请先安装阿里云 CLI: pip install aliyun-cli"

    # 创建安全组
    info "创建安全组..."
    SG_ID=$(aliyun ecs CreateSecurityGroup \
        --RegionId "$REGION" \
        --SecurityGroupName "bqt-sg" \
        --Description "BQT Trading Bot Security Group" \
        2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecurityGroupId'])")

    # 配置安全组规则
    for PORT in 22 80 443; do
        aliyun ecs AuthorizeSecurityGroup \
            --RegionId "$REGION" \
            --SecurityGroupId "$SG_ID" \
            --IpProtocol tcp \
            --PortRange "${PORT}/${PORT}" \
            --SourceCidrIp "0.0.0.0/0" \
            --Policy accept 2>/dev/null || true
    done
    ok "安全组创建完成: $SG_ID"

    # 查找可用的 VSwitch
    VSWITCH_ID=$(aliyun ecs DescribeVSwitches \
        --RegionId "$REGION" \
        2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
vswitches = data.get('VSwitches', {}).get('VSwitch', [])
if vswitches:
    print(vswitches[0]['VSwitchId'])
else:
    print('')
")

    if [[ -z "$VSWITCH_ID" ]]; then
        error "未找到 VSwitch，请先在阿里云控制台创建 VPC 和 VSwitch"
    fi

    # 生成随机密码
    ECS_PASSWORD="Bqt$(openssl rand -hex 8)!"

    # 创建实例
    info "创建 ECS 实例 (${INSTANCE_TYPE})..."
    INSTANCE_ID=$(aliyun ecs RunInstances \
        --RegionId "$REGION" \
        --ImageId "$IMAGE_ID" \
        --InstanceType "$INSTANCE_TYPE" \
        --SecurityGroupId "$SG_ID" \
        --VSwitchId "$VSWITCH_ID" \
        --InternetMaxBandwidthOut 5 \
        --InternetChargeType PayByTraffic \
        --InstanceChargeType PostPaid \
        --SystemDisk.Category cloud_essd \
        --SystemDisk.Size 40 \
        --Password "$ECS_PASSWORD" \
        --InstanceName "bqt-trading" \
        --HostName "bqt" \
        --Amount 1 \
        2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['InstanceIdSets']['InstanceIdSet'][0])")

    ok "实例创建成功: $INSTANCE_ID"
    info "等待实例启动..."

    # 等待实例运行
    for i in $(seq 1 30); do
        STATUS=$(aliyun ecs DescribeInstanceAttribute \
            --InstanceId "$INSTANCE_ID" \
            2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Status',''))")
        if [[ "$STATUS" == "Running" ]]; then
            break
        fi
        sleep 10
    done

    # 获取公网 IP
    HOST=$(aliyun ecs DescribeInstanceAttribute \
        --InstanceId "$INSTANCE_ID" \
        2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
ips = data.get('PublicIpAddress', {}).get('IpAddress', [])
print(ips[0] if ips else '')
")

    if [[ -z "$HOST" ]]; then
        # 如果没有公网 IP，尝试分配 EIP
        info "分配弹性公网 IP..."
        EIP_RESULT=$(aliyun ecs AllocateEipAddress \
            --RegionId "$REGION" \
            --Bandwidth 5 \
            --InternetChargeType PayByTraffic \
            2>/dev/null)
        EIP_ID=$(echo "$EIP_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['AllocationId'])")
        HOST=$(echo "$EIP_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['EipAddress'])")

        aliyun ecs AssociateEipAddress \
            --AllocationId "$EIP_ID" \
            --InstanceId "$INSTANCE_ID" \
            --RegionId "$REGION" 2>/dev/null
    fi

    echo ""
    ok "========================================="
    ok "  ECS 实例信息"
    ok "========================================="
    echo -e "  实例 ID:  ${GREEN}${INSTANCE_ID}${NC}"
    echo -e "  公网 IP:  ${GREEN}${HOST}${NC}"
    echo -e "  用户名:   ${GREEN}root${NC}"
    echo -e "  密码:     ${GREEN}${ECS_PASSWORD}${NC}"
    echo -e "  区域:     ${GREEN}${REGION}${NC}"
    echo ""
    warn "请妥善保存以上信息！"
    echo ""

    # 等待 SSH 可用
    info "等待 SSH 服务就绪..."
    for i in $(seq 1 30); do
        if ssh $SSH_OPTS "${USER}@${HOST}" "echo ok" 2>/dev/null; then
            break
        fi
        sleep 10
    done
}

# ============ 上传并部署 ============
deploy_to_server() {
    [[ -z "$HOST" ]] && error "请指定 --host 或使用 --create-ecs"

    build_ssh_opts

    info "测试 SSH 连接到 ${USER}@${HOST}:${SSH_PORT}..."
    ssh $SSH_OPTS "${USER}@${HOST}" "echo 'SSH 连接成功'" || error "SSH 连接失败，请检查 IP/用户名/密钥"

    # 打包项目（排除 node_modules、.git 等）
    info "打包项目文件..."
    TARBALL="/tmp/bqt-deploy-$(date +%s).tar.gz"
    tar -czf "$TARBALL" \
        -C "$PROJECT_DIR" \
        --exclude='node_modules' \
        --exclude='.git' \
        --exclude='frontend/node_modules' \
        --exclude='frontend/dist' \
        --exclude='__pycache__' \
        --exclude='.env' \
        --exclude='*.pyc' \
        .

    ok "打包完成: $(du -h "$TARBALL" | cut -f1)"

    # 上传
    info "上传到服务器..."
    scp $SCP_OPTS "$TARBALL" "${USER}@${HOST}:/tmp/bqt-deploy.tar.gz"
    ok "上传完成"

    # 远程部署
    info "远程执行部署..."
    ssh $SSH_OPTS "${USER}@${HOST}" bash <<'REMOTE_EOF'
set -euo pipefail

PROJECT_DIR="/opt/bqt"
mkdir -p "$PROJECT_DIR"

# 解压项目
tar -xzf /tmp/bqt-deploy.tar.gz -C "$PROJECT_DIR"
rm -f /tmp/bqt-deploy.tar.gz

# 执行 setup 脚本
chmod +x "${PROJECT_DIR}/deploy/aliyun/setup.sh"
bash "${PROJECT_DIR}/deploy/aliyun/setup.sh"
REMOTE_EOF

    # 清理本地临时文件
    rm -f "$TARBALL"

    echo ""
    ok "========================================="
    ok "  部署完成！"
    ok "========================================="
    echo ""
    echo -e "  ${GREEN}访问地址:${NC}  http://${HOST}"
    echo -e "  ${GREEN}API 文档:${NC}  http://${HOST}/docs"
    echo ""
}

# ============ 主流程 ============
main() {
    info "BQT 阿里云部署工具"
    info "项目目录: ${PROJECT_DIR}"
    echo ""

    if [[ "$CREATE_ECS" == "true" ]]; then
        create_ecs_instance
    fi

    deploy_to_server
}

main "$@"

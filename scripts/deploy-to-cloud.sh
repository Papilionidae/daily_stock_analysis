#!/usr/bin/env bash
# ===================================
# 一键部署到 Linux 云服务器
# ===================================
#
# 适用：Ubuntu 22.04+ / Debian 12+ 的全新云服务器
# 作用：
#   1. 安装 Docker + Docker Compose v2
#   2. 配置国内云厂商镜像加速（可选）
#   3. 克隆/更新 daily_stock_analysis 代码
#   4. 准备 .env（用现有模板或拉取）
#   5. 构建并启动 Web + 钉钉 bot + 每日定时推送
#   6. 验证容器和钉钉 Stream 连通性
#
# 用法：
#   # 远程登录到云服务器后，跑这条命令
#   curl -fsSL https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/scripts/deploy-to-cloud.sh | bash
#
#   # 或下载后执行
#   wget -O deploy.sh https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/scripts/deploy-to-cloud.sh
#   chmod +x deploy.sh
#   ./deploy.sh
#
# 可选环境变量：
#   REPO_URL              仓库地址（默认官方）
#   REPO_BRANCH           分支（默认 main）
#   INSTALL_DIR           安装目录（默认 /opt/daily_stock_analysis）
#   DOCKER_MIRROR         Docker 镜像加速地址（默认空，跳过）
#   APT_MIRROR            Debian APT 源镜像（默认 mirrors.aliyun.com，适合国内云服务器）
#   PIP_MIRROR            PyPI 镜像（默认 mirrors.aliyun.com，适合国内云服务器）
#   SKIP_DOCKER_INSTALL   设为 1 跳过 Docker 安装
#   SKIP_BUILD            设为 1 跳过镜像构建（用已有镜像）
#   SKIP_GIT              设为 1 跳过 git 操作（手动 COPY 代码时用）
#   ENV_SOURCE            本地 .env 路径（默认空，提示手动创建）
# ===================================

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/ZhuLinsen/daily_stock_analysis.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/daily_stock_analysis}"
DOCKER_MIRROR="${DOCKER_MIRROR:-}"
APT_MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"
PIP_MIRROR="${PIP_MIRROR:-mirrors.aliyun.com}"
SKIP_DOCKER_INSTALL="${SKIP_DOCKER_INSTALL:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_GIT="${SKIP_GIT:-0}"
ENV_SOURCE="${ENV_SOURCE:-}"
GIT_CLEAN_CONFIRM="${GIT_CLEAN_CONFIRM:-}"

log()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[ERR ]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        err "此脚本需要 root 权限，请用 sudo 或 root 用户执行"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VER="${VERSION_ID:-unknown}"
        OS_CODENAME="${VERSION_CODENAME:-unknown}"
    else
        err "无法识别操作系统（缺少 /etc/os-release）"
        exit 1
    fi
    log "检测到系统：${OS_ID} ${OS_VER} (${OS_CODENAME})"
    case "${OS_ID}" in
        ubuntu|debian) ;;
        *) warn "未在 Ubuntu/Debian 上充分测试，可能需要手动调整" ;;
    esac
}

install_docker() {
    if command -v docker >/dev/null 2>&1; then
        log "Docker 已安装：$(docker --version)"
    else
        log "安装 Docker..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sh /tmp/get-docker.sh
        ok "Docker 安装完成：$(docker --version)"
    fi

    if docker compose version >/dev/null 2>&1; then
        log "Docker Compose v2 已安装：$(docker compose version --short)"
    else
        log "安装 Docker Compose v2..."
        apt-get update -qq
        apt-get install -y docker-compose-plugin
        ok "Docker Compose v2 安装完成"
    fi

    # 让当前用户（非 root）也能用 docker
    if [ -n "${SUDO_USER:-}" ]; then
        usermod -aG docker "${SUDO_USER}"
        log "已将 ${SUDO_USER} 加入 docker 用户组（重连 SSH 后生效）"
    fi
}

configure_docker_mirror() {
    if [ -z "${DOCKER_MIRROR}" ]; then
        log "跳过 Docker 镜像加速（未设 DOCKER_MIRROR）"
        return
    fi
    log "配置 Docker 镜像加速：${DOCKER_MIRROR}"
    mkdir -p /etc/docker

    # 合并而非覆盖：保留 log-driver / data-root / insecure-registries 等既有键
    if [ -f /etc/docker/daemon.json ]; then
        if command -v jq >/dev/null 2>&1; then
            tmp=$(mktemp)
            if jq --arg mirror "${DOCKER_MIRROR}" \
                '.registry-mirrors = ((.registry-mirrors // []) + [$mirror] | unique)' \
                /etc/docker/daemon.json > "$tmp"; then
                mv "$tmp" /etc/docker/daemon.json
                log "已合并 DOCKER_MIRROR 到现有 daemon.json"
            else
                rm -f "$tmp"
                warn "现有 /etc/docker/daemon.json 不是合法 JSON，跳过合并。手动检查后再跑。"
                return
            fi
        else
            warn "未安装 jq，无法安全合并 /etc/docker/daemon.json。保留现有配置，跳过镜像加速。"
            return
        fi
    else
        cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["${DOCKER_MIRROR}"]
}
EOF
    fi
    systemctl restart docker
    ok "Docker 镜像加速已生效"
}

clone_or_pull_repo() {
    if [ "${SKIP_GIT}" = "1" ]; then
        log "跳过 git 操作（SKIP_GIT=1）"
        return
    fi

    if [ -d "${INSTALL_DIR}/.git" ]; then
        log "检测到已有代码目录，更新代码..."
        cd "${INSTALL_DIR}"
        git fetch --all

        # 优先使用 origin/${REPO_BRANCH}，不存在则回退到当前分支的跟踪远程
        local reset_target="origin/${REPO_BRANCH}"
        if ! git rev-parse "${reset_target}" >/dev/null 2>&1; then
            local current_branch
            current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
            reset_target="origin/${current_branch}"
            if [ -z "${current_branch}" ] || ! git rev-parse "${reset_target}" >/dev/null 2>&1; then
                err "无法确定远程分支。请设置 REPO_BRANCH 或手动更新。"
                exit 1
            fi
            warn "origin/${REPO_BRANCH} 不存在，使用当前分支 ${reset_target}"
        fi
        git reset --hard "${reset_target}"

        # 先 dry-run 列出将被清理的未跟踪文件，给用户一个机会看清楚
        if [ "${GIT_CLEAN_CONFIRM}" = "1" ]; then
            log "将被 git clean 移除的文件（dry-run）："
            git clean -ndx -e .env -e data -e logs -e reports -e longbridge_tokens || true
            warn "确认要删除以上文件吗？10 秒后继续（Ctrl-C 中止）..."
            sleep 10
        fi
        git clean -fdx -e .env -e data -e logs -e reports -e longbridge_tokens
    else
        log "克隆代码到 ${INSTALL_DIR}..."
        mkdir -p "$(dirname "${INSTALL_DIR}")"
        git clone --branch "${REPO_BRANCH}" --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
    fi
    ok "代码就绪：${INSTALL_DIR}"
}

prepare_env() {
    cd "${INSTALL_DIR}"

    if [ -f .env ]; then
        log ".env 已存在，跳过创建"
    elif [ -n "${ENV_SOURCE}" ] && [ -f "${ENV_SOURCE}" ]; then
        log "从 ${ENV_SOURCE} 复制 .env"
        cp "${ENV_SOURCE}" .env
    else
        warn ".env 不存在！创建模板："
        cp .env.example .env
        err "请在继续之前手动编辑 ${INSTALL_DIR}/.env 填入真实配置："
        err "  - STOCK_LIST"
        err "  - LLM_* / LITELLM_MODEL（Agnes 或其他）"
        err "  - DINGTALK_APP_KEY / DINGTALK_APP_SECRET / DINGTALK_STREAM_ENABLED=true"
        err "  - TUSHARE_TOKEN（可选）"
        err "  - WECHAT_WEBHOOK_URL / EMAIL_*（可选）"
        err "  - WEBUI_HOST=0.0.0.0（容器要求）"
        read -rp "按回车继续（确认已编辑 .env），或 Ctrl+C 退出..."
    fi

    # 关键：WEBUI_HOST 必须是 0.0.0.0 才能从容器外访问
    if grep -qE '^WEBUI_HOST=127\.0\.0\.1' .env; then
        warn "检测到 WEBUI_HOST=127.0.0.1，Docker 容器要求改为 0.0.0.0"
        sed -i 's/^WEBUI_HOST=127\.0\.0\.1/WEBUI_HOST=0.0.0.0/' .env
        ok "已自动改为 WEBUI_HOST=0.0.0.0"
    fi
}

build_images() {
    if [ "${SKIP_BUILD}" = "1" ]; then
        log "跳过镜像构建（SKIP_BUILD=1）"
        return
    fi
    cd "${INSTALL_DIR}"
    log "构建 Docker 镜像（首次 5-10 分钟）..."
    export APT_MIRROR PIP_MIRROR
    docker compose -f docker/docker-compose.yml build \
        --build-arg "APT_MIRROR=${APT_MIRROR}" \
        --build-arg "PIP_MIRROR=${PIP_MIRROR}"
    ok "镜像构建完成"
}

start_services() {
    cd "${INSTALL_DIR}"
    log "启动 server 容器（Web + 钉钉 bot）..."
    docker compose -f docker/docker-compose.yml up -d server

    log "启动 analyzer 容器（每日定时推送）..."
    docker compose -f docker/docker-compose.yml up -d analyzer

    log "等待 5 秒让服务就绪..."
    sleep 5

    docker compose -f docker/docker-compose.yml ps
}

verify_deployment() {
    cd "${INSTALL_DIR}"
    log "===== 部署验证 ====="

    # 1. 容器状态
    if ! docker ps --format '{{.Names}}' | grep -q '^stock-server$'; then
        err "stock-server 容器未运行！"
        docker logs stock-server --tail 30
        return 1
    fi
    ok "stock-server 容器运行中"

    if ! docker ps --format '{{.Names}}' | grep -q '^stock-analyzer$'; then
        warn "stock-analyzer 容器未运行（可忽略）"
    else
        ok "stock-analyzer 容器运行中"
    fi

    # 2. Web 健康
    if docker exec stock-server curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
        ok "Web 服务健康（http://localhost:8000）"
    else
        warn "Web 健康检查失败，看日志："
        docker logs stock-server --tail 20
    fi

    # 3. 钉钉 Stream 连通
    if docker logs stock-server 2>&1 | grep -qE "DingTalk.*等待消息"; then
        ok "钉钉 Stream 客户端已启动"
    else
        warn "未发现钉钉 Stream 启动日志"
    fi

    if docker logs stock-server 2>&1 | grep -qE "(401|authFailed|授权失败)"; then
        err "钉钉鉴权失败（401 / authFailed）！请检查 .env 中的 AppKey/AppSecret"
        return 1
    fi

    log "===== 验证完成 ====="
    log "接下来请："
    log "  1. 打开钉钉 → 工作台 → 搜你的应用名 → 私聊发 /help"
    log "  2. SSH 端口转发访问 Web：ssh -L 8000:127.0.0.1:8000 user@this-server"
    log "     然后本机浏览器开 http://127.0.0.1:8000"
    log "  3. 跟踪日志：docker logs -f stock-server"
}

main() {
    require_root
    detect_os

    if [ "${SKIP_DOCKER_INSTALL}" != "1" ]; then
        install_docker
    else
        log "跳过 Docker 安装（SKIP_DOCKER_INSTALL=1）"
    fi

    configure_docker_mirror
    clone_or_pull_repo
    prepare_env
    build_images
    start_services
    verify_deployment

    ok "部署完成！"
}

main "$@"

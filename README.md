# NanoQA 测试管理系统

AI 原生的测试用例管理 / 测试执行 / 缺陷协同平台。以「需求 → 用例 → 计划 → 执行 → 缺陷 → 报告」质量闭环为主线，覆盖模块树与版本化用例、快捷键执行、缺陷状态机与多维关联、ECharts 报告、CSV / XLSX 导入导出、命令面板、角色权限矩阵与审计日志，并内置 AI 生成用例留桩（MockProvider + 人工审核入库）。

---

## 目录

- [功能全景](#功能全景)
- [质量闭环](#质量闭环)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [数据模型](#数据模型)
- [API 参考](#api-参考)
- [前端说明](#前端说明)
- [快捷键](#快捷键)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [测试](#测试)
- [性能基线](#性能基线)
- [冒烟与工具脚本](#冒烟与工具脚本)
- [Docker 部署](#docker-部署)
- [开发规范](#开发规范)
- [常见问题](#常见问题)

---

## 功能全景

**需求管理**
- 需求 CRUD、优先级 / 状态、需求 ↔ 用例关联（批量关联 / 解除）
- 覆盖率面板：未覆盖 / 已覆盖 / 部分覆盖、关联用例数、关联缺陷数

**用例管理**
- 模块树（三级，支持移动 / 重组）、标签、优先级 / 类型 / 状态、负责人
- 步骤编辑器（步骤 / 预期结果逐条编辑、拖拽排序）、预置条件、预期结果
- 版本历史：每次修改生成版本快照，可对比 / 回看任意版本
- 操作历史：字段级变更记录，与审计日志联动
- 批量操作：移动模块 / 打标签 / 归档 / 删除；用例复制、软删除与恢复
- 导入导出：CSV / XLSX；导入为「上传 → 字段映射 → 预览校验 → 确认」四步向导，非法行逐行报错可跳过；导出按当前筛选条件

**测试计划与执行**
- 计划内选例（按模块 / 标签 / 优先级筛选）、分配执行人
- 执行页快捷键提交结果：P 通过 / F 失败 / B 阻塞 / S 跳过 / N 未执行；F 自动弹缺陷表单并回链执行结果
- 版本快照：结果固定在执行时的用例版本，用例后续修改不影响历史结果
- 批量提交结果（bulk）、执行轮次（Run）维度管理

**缺陷协同**
- 缺陷状态机（转为处理中 / 已拒绝 / 重复 / 已关闭等合法目标按钮驱动，非法转移拒绝）
- 缺陷 ↔ 用例 / 执行结果 / 需求多维关联；归档仅系统管理员

**报告与工作台**
- 项目 Dashboard：用例 / 需求 / 计划 / 缺陷六项概览、审计动态、快捷入口
- 测试报告：执行结果分布、模块通过率、模块分析、失败用例、缺陷统计（ECharts）
- 工作台：个人待办 / 快捷入口 / 项目动态

**平台能力**
- 命令面板（Ctrl+K）：页面 / 项目 / 用例 / 缺陷四组检索，防抖搜索
- 成员管理、系统角色（admin / pm / qa / dev / viewer）、27 权限矩阵可视化
- 审计日志：对象维度变更 diff、类型筛选、时间筛选
- AI 生成用例：MockProvider 留桩（生成 / 重复检测 / 需求分析 / 缺陷分析 / 扩展），产出进 AITask 待审核队列，人工 accept / reject 后入库
- 附件上传 / 下载 / 删除（项目维度）

## 质量闭环

```
需求（Requirement）──关联──▶ 用例（TestCase）
                                │ 挑选入
                                ▼
                        计划（TestPlan）──发起──▶ 执行轮次（TestRun）
                                                    │ 逐条提交
                                                    ▼
                                            结果（TestResult）─FAIL─▶ 缺陷（Defect）
                                                    │                   │
                                                    └────── 报告 ◀──────┘
                                                        （覆盖 / 通过率 / 缺陷统计）
```

- 编号体系：`<项目KEY>-TC-000001 / -REQ- / -BUG-`，由 `NumberSequence` 取号，单调递增、永不复用
- 每一步操作落入审计日志（object_type / object_id / action / diff）

## 系统架构

```
┌──────────────────────────────────────────────┐
│  Vue 3 + TS + Element Plus + ECharts         │
│  Pinia(状态) / vue-router(路由) / axios(信封) │
└──────────────────┬───────────────────────────┘
                   │ /api/v1/*（JWT Bearer + 统一信封）
┌──────────────────▼───────────────────────────┐
│  Django 6 + DRF + SimpleJWT                   │
│  apps: accounts organizations projects        │
│        requirements testcases testplans       │
│        executions defects reports ai          │
│        audit attachments                      │
│  common: 信封 / 状态机 / 乐观锁 / 权限 / 取号   │
└──────────────────┬───────────────────────────┘
                   │
        PostgreSQL 18        Redis（可选：缓存 / 限流）
```

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3.5 + TypeScript + Vite 8 + Pinia + Element Plus（按需引入）+ vue-router + ECharts 6 |
| 后端 | Django 6 + DRF + SimpleJWT |
| 数据库 | PostgreSQL 18（Redis 可选，用于缓存 / 限流） |
| 部署 | docker-compose（db / redis / backend / frontend-nginx） |

## 数据模型

| 域 | 实体 | 说明 |
| --- | --- | --- |
| 账号权限 | User / Role / Permission / RolePermission | 5 个系统角色 × 27 权限；User 可标记系统管理员 |
| 组织 | Organization / OrganizationMember | 组织与组织级角色 |
| 项目 | Project / ProjectMember / Module / Tag | 模块三级树（支持 move）、标签、项目成员角色 |
| 需求 | Requirement / RequirementTestCase | 需求与用例多对多 |
| 用例 | TestCase / TestCaseVersion / TestCaseTag | 版本快照 + 步骤（order/action/expected） |
| 计划 | TestPlan / TestPlanCase | 计划选例与分配 |
| 执行 | TestRun / TestResult | Run 与逐条结果（版本快照） |
| 缺陷 | Defect / TestCaseDefect / TestResultDefect / RequirementDefect | 缺陷与用例 / 结果 / 需求关联 |
| 平台 | Attachment / AITask / AuditLog / NumberSequence | 附件、AI 任务队列、审计、编号序列 |

## API 参考

前缀 `/api/v1/`，除 `auth/login`、`auth/refresh`、`ping` 外均需 `Authorization: Bearer <access>`。

**认证与账号**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `ping/` | 健康检查 |
| POST | `auth/login/` | 登录（email + password，返回 access / refresh） |
| POST | `auth/refresh/` | 刷新令牌 |
| POST | `auth/logout/` | 登出 |
| GET | `auth/me/` | 当前用户与权限 |
| GET | `users/` | 用户列表 |
| GET/POST | `roles/` | 角色与权限矩阵 |
| GET/PATCH/DELETE | `roles/{id}/` | 角色详情（系统角色不可删） |

**项目 / 组织**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `projects/` | 项目列表 / 创建 |
| GET/PATCH/DELETE | `projects/{id}/` | 项目详情（PATCH 带 `updated_at` 乐观锁） |
| GET/POST | `projects/{id}/members/`、`projects/members/{id}/` | 项目成员 |
| GET/POST | `projects/{id}/modules/`、`modules/{id}/`、`modules/{id}/move/` | 模块树 |
| GET/POST | `projects/{id}/tags/`、`tags/{id}/` | 标签 |
| — | `organizations/...` | 组织与组织成员（同构） |

**用例**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `projects/{id}/testcases/` | 列表（q / status / priority / module / tag 筛选分页）/ 创建 |
| POST | `projects/{id}/testcases/batch/` | 批量操作 |
| GET | `projects/{id}/export/testcases/?format=csv\|xlsx` | 按筛选导出 |
| POST | `projects/{id}/import/testcases/` | 导入（预览 / 确认两段式） |
| GET/PATCH/DELETE | `testcases/{id}/` | 详情 / 编辑（乐观锁）/ 软删除 |
| POST | `testcases/{id}/restore\|duplicate\|move/` | 恢复 / 复制 / 移动 |
| GET | `testcases/{id}/versions/`、`testcases/{id}/history/` | 版本历史 / 操作历史 |
| GET | `testcase-versions/{id}/` | 版本快照详情 |

**需求 / 计划 / 执行 / 缺陷**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `projects/{id}/requirements/`、`requirements/{id}/` | 需求 CRUD |
| POST/DELETE | `requirements/{id}/testcases/`、`requirements/{id}/testcases/{case}/` | 需求-用例关联 |
| GET | `requirements/{id}/coverage/` | 覆盖率面板 |
| GET/POST | `projects/{id}/testplans/`、`testplans/{id}/` | 计划 CRUD |
| GET/POST | `testplans/{id}/cases/`、`testplans/{id}/cases/{case}/` | 计划选例 / 分配 |
| POST | `testplans/{id}/start/` | 发起执行轮次 |
| GET/POST | `testplans/{id}/runs/`、`runs/{id}/` | Run 列表 / 详情 |
| GET/POST | `runs/{id}/results/`、`runs/{id}/results/bulk/` | 结果提交（单条 / 批量） |
| GET/PATCH | `results/{id}/` | 结果详情 / 状态修改 |
| POST | `results/{id}/defects/` | FAIL 时建缺陷并关联 |
| GET/POST | `projects/{id}/defects/`、`defects/{id}/` | 缺陷 CRUD（状态机约束） |
| POST/DELETE | `defects/{id}/testcases/`、`defects/{id}/requirements/` | 缺陷关联 |

**报告 / AI / 附件 / 审计**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `projects/{id}/dashboard/` | 项目概览聚合 |
| GET | `projects/{id}/reports/`、`runs/{id}/report/` | 报告列表 / Run 报告聚合 |
| POST | `ai/testcases/generate/`、`ai/testcases/detect-duplicates/` | AI 生成 / 重复检测 |
| POST | `ai/testcases/{id}/review/`、`ai/testcases/{id}/expand/` | 审核 / 扩展 |
| POST | `ai/requirements/{id}/analyze/`、`ai/defects/{id}/analyze/` | 需求 / 缺陷分析 |
| GET | `ai/tasks/`、`ai/tasks/{id}/accept\|reject/` | AI 任务队列与审核 |
| POST/GET/DELETE | `attachments/`、`attachments/{id}/download\|` | 附件 |
| GET | `projects/{id}/audit-logs/` | 审计日志 |

### 接口约定

统一响应信封：

```json
{ "code": 0, "message": "success", "data": { } }
```

分页统一：`{ "items": [], "total": 0, "page": 1, "page_size": 20 }`

| code | 含义 | HTTP |
| --- | --- | --- |
| 0 | 成功 | 200/201 |
| 40001 | 权限拒绝 | 403 |
| 40002 | 未认证 | 401 |
| 40003 | 乐观锁冲突 | 409 |
| 40004 | 状态机非法转移 | 400 |
| 40005 | 资源不存在 | 404 |
| 40006 | 参数校验错误 | 400 |
| 40007 | 业务规则冲突（如模块仍有用例） | 409 |
| 50000 | 服务器错误 | 500 |

**乐观锁**：PATCH 请求体需回传对象的 `updated_at` 原值，与库中不匹配返回 409 + `code 40003`，前端弹出冲突处理框。

**请求示例**

```powershell
# 登录
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ `
  -H "Content-Type: application/json" `
  -d '{"email": "admin@nanoqa.dev", "password": "Admin#12345"}'

# 拉取用例列表
curl http://127.0.0.1:8000/api/v1/projects/5/testcases/?page=1&page_size=20 `
  -H "Authorization: Bearer <access>"
```

## 前端说明

**路由表**（`/p/:projectId/*` 为项目上下文，切换项目自动携带）

| 路径 | 页面 |
| --- | --- |
| `/login` | 登录 |
| `/projects`、`/workbench` | 项目列表、工作台 |
| `/p/:id/overview` | 项目概览（六项概览 + 审计动态 + 快捷入口） |
| `/p/:id/testcases`、`/p/:id/testcases/:caseId` | 用例列表 / 详情 |
| `/p/:id/requirements`、`/p/:id/requirements/:reqId` | 需求列表 / 详情 |
| `/p/:id/testplans`、`/p/:id/testplans/:planId` | 计划列表 / 详情（选例、分配、发起执行） |
| `/p/:id/runs`、`/p/:id/runs/:runId`、`/p/:id/runs/:runId/report` | 执行列表 / 执行页 / 测试报告 |
| `/p/:id/defects`、`/p/:id/defects/:defectId` | 缺陷列表 / 详情 |
| `/p/:id/reports`、`/p/:id/ai` | 报告中心、AI 工作台 |
| `/p/:id/members`、`/p/:id/roles`、`/p/:id/audit` | 成员、权限矩阵、审计日志 |

**关键机制**
- `api/client.ts`：axios 封装统一解包信封；401 单飞刷新（并发只发一次 refresh）；40003 冲突弹框
- 设计令牌 `styles/tokens.css`（墨色灰阶 + 靛蓝强调）+ `element-override.scss` 映射 Element Plus 变量，禁止硬编码色值
- Element Plus 按需引入（unplugin）；`ElMessage` / `ElMessageBox` / `v-loading` 的样式在 `main.ts` 手动按需引入
- 跨项目 URL 守卫：路由资源与项目上下文不匹配时提示「资源不存在」，不串数据

## 快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+K` | 命令面板 |
| `?` | 快捷键帮助 |
| `g` + `p/t/d/r/l/e/m/a` | 跳转：项目 / 用例 / 缺陷 / 需求 / 计划 / 执行 / 成员 / 审计 |
| `P / F / B / S / N` | 执行页提交：通过 / 失败 / 阻塞 / 跳过 / 未执行 |

（执行页快捷键优先级高于全局 `g` 前缀，不会互相触发。）

## 目录结构

```
NanoQA/
├── backend/                    # Django 后端
│   ├── apps/
│   │   ├── accounts/           # 用户 / 角色 / 权限 / 登录（JWT）
│   │   ├── organizations/      # 组织与成员
│   │   ├── projects/           # 项目 / 成员 / 模块树 / 标签
│   │   ├── requirements/       # 需求与覆盖率
│   │   ├── testcases/          # 用例 / 版本 / 导入导出
│   │   ├── testplans/          # 计划 / 选例 / 分配
│   │   ├── executions/         # Run / 结果 / 批量提交
│   │   ├── defects/            # 缺陷 / 状态机 / 关联
│   │   ├── reports/            # Dashboard / 报告聚合
│   │   ├── ai/                 # AI 任务队列（MockProvider）
│   │   ├── audit/              # 审计日志
│   │   └── attachments/        # 附件
│   ├── common/                 # 信封 / 状态机 / 乐观锁 / 权限 / 取号
│   ├── config/                 # settings（base/development/production）+ urls
│   ├── scripts/                # smoke_api.py / seed_demo.py / perf_api.py
│   └── manage.py
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── api/                # axios 客户端（401 单飞刷新 / 40003 冲突弹框）
│       ├── components/         # ui/ 共享基元、CommandPalette
│       ├── views/              # 按业务域分目录（testcases/ executors/ reports/ …）
│       ├── stores/             # Pinia（auth 等）
│       ├── router/             # 路由表 + 登录守卫
│       └── styles/             # tokens.css 设计令牌 + element-override.scss
└── docker-compose.yml
```

## 快速开始

前提：Python 3.12+、Node 20+、PostgreSQL 18（默认连接 `postgres@127.0.0.1:5432`，库名 `nanoqa`）。

### 1. 后端

```powershell
cd backend
pip install -r requirements.txt
python manage.py migrate
python scripts/seed_demo.py        # 幂等演示数据（可选）
python manage.py runserver 8000
```

### 2. 前端

```powershell
cd frontend
npm install
npm run dev                        # http://localhost:5173，/api 代理到 127.0.0.1:8000
```

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | `nanoqa` / `postgres` / 空 / `127.0.0.1` / `5432` | 数据库连接 |
| `DB_CONN_MAX_AGE` | `60` | 连接复用秒数 |
| `DB_TEST_NAME` | `nanoqa_test` | 测试库名 |
| `DJANGO_SECRET_KEY` | `insecure-dev-key` | 生产必须覆盖 |
| `REDIS_URL` | 空 | 缓存 / 限流（不配则用本地内存） |
| `MEDIA_ROOT` | `backend/media` | 附件存储 |

### 演示账号

| 账号 | 密码 | 说明 |
| --- | --- | --- |
| admin@nanoqa.dev | Admin#12345 | 系统管理员，含演示项目 SHOP（用例 / 需求 / 计划 / Run / 缺陷） |

## 测试

```powershell
cd backend
# 全量后端测试（建议独立测试库名，避免 --keepdb 残留状态）
$env:DB_TEST_NAME="nanoqa_test_full"; python manage.py test apps --keepdb

# 单个应用
$env:DB_TEST_NAME="nanoqa_test_tc"; python manage.py test apps.testcases --keepdb
```

- 测试规模 232 条，覆盖用例 / 版本 / 计划 / 执行 / 缺陷 / 需求 / 导入导出 / 并发取号 / 状态机 / 权限，当前全部通过。
- 测试隔离：每个测试库独立命名；`TransactionTestCase` 的 flush 会截断数据迁移种子（Role/Permission），测试基座已内置自愈（`apps/accounts/tests/helpers.py::ensure_rbac_seed`），并发取号测试已开启 `serialized_rollback`。

## 性能基线

1000 用例夹具、每接口 30 次采样，实测：

| 接口 | P95 | 目标 | 判定 |
| --- | --- | --- | --- |
| 用例列表（分页 20） | 188 ms | < 500 ms | 达标 |
| 用例搜索 | 98 ms | < 500 ms | 达标 |
| 工作台 Dashboard | 186 ms | < 1 s | 达标 |
| 测试报告聚合 | 171 ms | < 500 ms | 达标 |
| 缺陷列表（分页 20） | 65 ms | < 500 ms | 达标 |

前端构建产物（Element Plus 按需引入后）：首屏主包 53 KB、首屏 CSS 11 KB。

## 冒烟与工具脚本

```powershell
cd backend
python scripts/smoke_api.py        # 全链路 API 冒烟：登录→项目→用例→需求→计划→执行→缺陷→报告（需 runserver 运行中）
python scripts/seed_demo.py        # 幂等演示数据（含 NumberSequence 推进）
python scripts/perf_api.py         # 性能核验（自动建 1000 用例夹具、采样、输出达标判定）
```

## Docker 部署

```powershell
docker compose up -d
```

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| db | 5432 | PostgreSQL 18 |
| redis | 6379 | 缓存 / 限流（可选） |
| backend | 8000 | Django（gunicorn） |
| frontend | 80 | nginx 静态托管 + 反代 `/api` 至 backend |

生产环境务必设置 `DJANGO_SECRET_KEY` 与数据库口令。

## 开发规范

- **响应信封**：所有写接口返回统一信封；前端 `api/client.ts` 统一解包、错误提示与 401 刷新，页面不自行解析响应。
- **设计令牌**：UI 颜色 / 间距 / 圆角 / 阴影一律取自 `tokens.css`，禁止硬编码色值；Element Plus 变量经 `element-override.scss` 映射。
- **编号取号**：用例 / 需求 / 缺陷编号由 `NumberSequence` 取号（`select_for_update`），单调递增、永不复用，并发安全。
- **状态流转**：统一走 `common/statemachine.py`，页面只渲染合法目标按钮，非法转移一律 40004 拒绝。
- **乐观锁**：所有编辑接口回传 `updated_at`，冲突 40003，前端弹冲突处理框。
- **审计**：业务写操作在同一事务内落审计日志（create / update / delete + diff），失败整体回滚。
- **按需引入**：Element Plus 组件样式由 unplugin 注入，JS API 与 `v-loading` 指令样式在 `main.ts` 手动补入，勿改回全量引入。

## 常见问题

**登录后 401 循环？**
检查后端是否运行在 8000 且 `vite.config.ts` 代理指向 `127.0.0.1:8000`；`auth/refresh` 失效会自动退回登录页。

**测试运行报 `Role.DoesNotExist`？**
测试库被 `TransactionTestCase` flush 过且使用了 `--keepdb` 残留状态。换一个全新的 `DB_TEST_NAME` 重跑；基座自愈也会在下次运行时自动补齐种子。

**新建对象报 500 且提示取号失败？**
演示数据直插的项目需推进 `NumberSequence`，运行 `python scripts/seed_demo.py`（幂等）即可修复。

**导入 XLSX 报错？**
确认文件不超 10MB、表头含「标题」列；导入向导第二步可手动映射字段，非法行会在预览步逐行标注并跳过。

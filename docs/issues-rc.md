# RC 里程碑 Issues（可复制至 GitHub）

---

**标题**: [P1][RC][qa] 压测与性能验收（API/SSE/前端首屏）  
**Labels**: type:task, module:qa, priority:P1, milestone:RC

**Scope**
- API p95（命中 ≤ 200ms，未命中 ≤ 600ms）
- SSE 端到端延迟 ≤ 1s；保活与重连稳定
- 前端首屏 ≤ 2s；交互流畅

**Acceptance (SMART)**
- 压测报告达标；问题清单与修复记录齐备

**KPIs**
- 接口错误率 ≤ 0.1%；保活 ≥ 1h；重连成功率 ≥ 99%

**Dependencies**
- Alpha/Beta 功能完整

**Estimate**
- QA 1 人 / 3 天

**Links**
- docs/test-plan.md

---

**标题**: [P1][RC][security] 安全审查与合规（鉴权/RBAC/审计）  
**Labels**: type:task, module:api, priority:P1, milestone:RC

**Scope**
- 鉴权与 RBAC 策略验证（命名空间/容器）
- 审计日志与访问控制清单；漏洞扫描（基础）

**Acceptance (SMART)**
- 安全审查报告通过；审计条目完整

**KPIs**
- 未授权阻断率=100%；漏洞扫描高危=0

**Dependencies**
- 鉴权/RBAC 上线

**Estimate**
- 1 人 / 2 天

**Links**
- docs/backend-api-contract.md

---

**标题**: [P1][RC][devops] 发布与回滚演练（文档与脚本）  
**Labels**: type:task, module:devops, priority:P1, milestone:RC

**Scope**
- 发布流程文档与脚本；回滚方案演练
- 版本标记与变更日志

**Acceptance (SMART)**
- 演练通过；文档齐备；风险可控

**KPIs**
- 发布失败率 ≤ 1%；回滚成功率=100%

**Dependencies**
- CI/CD 完成；镜像构建稳定

**Estimate**
- 0.5 人 / 2 天

**Links**
- .github/workflows/*.yml

---

**标题**: [P1][RC][qa] 缺陷收敛与最终验收（告警相关 P1=0）  
**Labels**: type:task, module:qa, priority:P1, milestone:RC

**Scope**
- P1 缺陷清零；P2 ≤ 2；回归通过
- 验收标准与签字流程

**Acceptance (SMART)**
- 验收报告通过；里程碑关闭

**KPIs**
- 回归通过率 ≥ 99%

**Dependencies**
- 所有功能与接口稳定

**Estimate**
- QA 1 人 / 2 天

**Links**
- docs/roadmap.md

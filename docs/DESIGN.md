# K8s 自愈 AI Agent — 深度设计文档

> 完整设计文档见：`D:\xx_yw002\07_K8s自愈AI_Agent_深度设计文档.md`
>
> 本文档为项目实现时的快速参考。

---

## 设计原则

1. **AI 做判断，代码做执行** — AI 不直接操作 K8s
2. **安全优先** — 置信度门槛 + 回滚机制
3. **人类兜底** — AI 不确定时自动升级
4. **全程可审计** — 每次操作都记录

---

## 架构

```
AlertManager Webhook → FastAPI
  → Diagnosis Engine (K8s 数据收集)
  → AI Analysis Engine (Claude API)
  → Decision Engine (置信度分流)
  → Healing Executor (修复执行) / Human Approval (人工审批) / Notify Only (仅通知)
  → Verification Engine (验证)
  → Audit Log + Notification
```

---

## 安全五层模型

| Layer | 机制 |
|-------|------|
| 1 | K8s RBAC 最小权限 |
| 2 | Namespace 白名单 |
| 3 | 动作白名单 |
| 4 | 置信度门槛 |
| 5 | 人工兜底 + 修复循环保护 |

---

## Prompt 工程

- System Prompt: SRE 专家角色锚定 + 故障模式速查表 + 安全约束
- User Prompt: 结构化诊断数据（Pod Status + Events + Logs + Resources）
- 输出: JSON Schema 约束（root_cause, fix_type, confidence, evidence, fix_params）
- 验证: 五道防线（结构校验、白名单校验、范围校验、一致性校验、禁止操作检测）

---

## 验收标准

| 指标 | 目标 |
|------|------|
| OOMKilled 自动修复成功率 | ≥ 90% |
| 告警到修复耗时 | ≤ 30s |
| AI 诊断置信度 ≥ 0.8 占比 | ≥ 70% |
| 误修复率 | 0% |
| 修复循环发生率 | 0% |

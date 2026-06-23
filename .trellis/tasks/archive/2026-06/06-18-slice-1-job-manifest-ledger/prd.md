# Slice 1: job manifest 最小总账本

## Goal

建立 `job_manifest.json` 的最小可用能力，让每个 job 有一个统一总入口记录状态、用户态摘要、artifact 清单和验证状态。

## Why

当前 job 目录里有多个看似真源的文件，agent 容易扫描目录、猜路径、把系统内部产物当用户交付物。这个 slice 先解决统一入口问题，不迁移旧目录。

## Scope

- 新增 `schemas/job_manifest.schema.json`。
- 新增共享 helper，例如 `runtime/job_manifest.py`。
- 支持初始化 manifest、读取 manifest、登记 step、登记 artifact、更新 user surface、校验 manifest。
- artifact path 必须是 job 内相对路径，并防止 path escape。
- 写入必须 atomic。
- CLI 面向 agent 时输出 JSON-only。

## Non-goals

- 不移动旧 job 文件。
- 不接入所有 skill。
- 不压缩或删除任何证据文件。

## Acceptance Criteria

- [x] 新 job 目录可创建 `job_manifest.json`。
- [x] 可登记一个 `user_deliverable` 和一个 `derived_internal` artifact。
- [x] 用户态清单只返回 `user_visible=true` 的 artifact。
- [x] `../` 或绝对路径 escape 会校验失败。
- [x] helper 的成功和失败输出稳定可解析。

## Dependencies

None.

## Validation

- `python3 -m py_compile runtime/job_manifest.py`
- manifest helper focused tests
- path escape negative test

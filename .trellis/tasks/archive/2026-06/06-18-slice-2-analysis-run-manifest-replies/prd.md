# Slice 2: analysis-run manifest 接入与回复降噪

## Goal

让 `RA:analysis-run` 成为 job 生命周期 owner：初始化或恢复 job 时确保 manifest 存在，最终回复默认从 `user_surface` 生成。

## Why

只建 manifest 不够。如果 analysis-run 仍然按旧方式回复路径和过程文件，用户态体验不会改善。

## Scope

- job 初始化时创建 manifest。
- 旧 job 恢复时补 manifest，不移动旧文件。
- 每个关键阶段更新 step 状态。
- 最终 completion summary 默认输出业务摘要、交付物、验证状态、风险和下一步。
- 内部路径、脚本名、source key 只在用户要求技术详情时输出。
- `.meta/artifact_index.json` 保留兼容，但登记为 legacy。

## Non-goals

- 不改 report 生成逻辑。
- 不改 data-export / data-profile 写入路径。

## Acceptance Criteria

- [x] 新 job 初始化后 manifest 存在。
- [x] 旧 job 缺 manifest 时能补建，不破坏旧文件。
- [x] 最终回复可由 manifest 的 `user_surface` 渲染。
- [x] 默认回复不包含内部目录、脚本名、source key。

## Dependencies

- Slice 1

## Validation

- analysis-run init/resume smoke
- user surface rendering test
- legacy artifact index compatibility smoke

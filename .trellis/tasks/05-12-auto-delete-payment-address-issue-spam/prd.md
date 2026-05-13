# brainstorm: auto delete Payment Address issue spam

## Goal

为公开仓库增加一个 issue / issue comment 自动检查，命中 `Payment Address` 垃圾内容时自动处理，减少诈骗评论留在公开页面上的时间。

## What I Already Know

* 用户已确认 `idan57570-art` 评论包含 `Payment Address`，属于垃圾评论/诈骗引流。
* 评论可以通过 GitHub REST API 删除。
* issue 正文不走普通删除路径；MVP 用关闭并清理正文来降低公开影响。

## Assumptions

* 只匹配 `Payment Address`，不做泛化反垃圾分类，降低误删风险。
* 使用仓库默认 `GITHUB_TOKEN`，不引入高权限 PAT。

## Requirements

* 监听新建/编辑 issue comment。
* 监听新建/编辑 issue body。
* comment 命中 `Payment Address` 时直接删除。
* issue body 命中时关闭并替换正文。
* 本地脚本可以 dry-run 和单元测试。

## Acceptance Criteria

* [ ] GitHub Actions workflow 覆盖 `issues` 与 `issue_comment` 事件。
* [ ] moderation 逻辑有 focused unit tests。
* [ ] workflow 权限保持最小，只给 `issues: write`。
* [ ] 文档说明自动化边界。

## Out of Scope

* 不做 ML/LLM spam detection。
* 不自动 block GitHub 用户，因为 block 需要个人 `user` scope，不适合放仓库 Actions。

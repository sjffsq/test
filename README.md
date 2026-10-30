# Tiny Expense · 轻量记账工具

一个使用 Python 标准库实现的命令行记账项目，支持新增支出、列出记录和按月分类汇总。金额使用 `Decimal`，记录保存为本地 JSON 文件，无第三方运行依赖。

**本项目特意保留一个用于练习排查的小 bug：月度汇总会漏算当月最后一天的支出。** 详情见下方 BUG-001。

## 运行

需要 Python 3.10 或更新版本。在项目根目录执行：

```bash
python -m expense_tracker add 25.50 --category 餐饮 --date 2026-10-15 --note 午餐
python -m expense_tracker add 8.00 --category 交通 --date 2026-10-16
python -m expense_tracker list
python -m expense_tracker summary --month 2026-10
```

默认使用当前目录下的 `expenses.json`。可以通过全局参数 `--data` 指定其他文件；该参数放在子命令前：

```bash
python -m expense_tracker --data ./data/personal.json add 12.30 --category 餐饮
python -m expense_tracker --data ./data/personal.json list
```

`add` 的日期默认为当天，分类默认为“其他”；`summary` 的月份默认为本月。金额必须大于零、最多两位小数，且不能超过 999999999.99。所有金额按人民币元理解，不支持混合币种。

也可在虚拟环境中运行 `python -m pip install -e .`，安装后使用 `tiny-expense` 命令。

## 已知小 bug：BUG-001

**现象：月度汇总漏算月末最后一天，记录本身仍然存在，`list` 可以正常看到。**

在一个尚不存在的演示数据文件上运行以下命令（重复演示前删除该演示文件，避免重复记账）：

```bash
python -m expense_tracker --data demo-expenses.json add 10.00 --category 餐饮 --date 2026-10-30
python -m expense_tracker --data demo-expenses.json add 20.00 --category 餐饮 --date 2026-10-31
python -m expense_tracker --data demo-expenses.json list
python -m expense_tracker --data demo-expenses.json summary --month 2026-10
```

- 预期汇总：2 笔，总计 30.00 元。
- 实际汇总：1 笔，总计 10.00 元；10 月 31 日的 20.00 元被漏算。
- 影响：所有月份的最后一天，包括闰年 2 月 29 日。分类金额与总笔数也会同步少计。
- 原因：`expense_tracker/core.py` 的 `summarize_month()` 将结束日期设置为当月最后一天，却用 `< end` 过滤，排除了这一天。
- 修复提示：将该过滤条件改为 `start <= expense.spent_on <= end`，然后移除对应测试的 `@unittest.expectedFailure`。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖 JSON 持久化、中文字段、金额校验、文件损坏保护、跨月过滤及命令行功能。BUG-001 有独立的 `expectedFailure` 测试，断言的是正确行为，因此当前运行结果会包含 **1 个预期失败**。修复后若未移除该标记，测试会报告 `unexpected success`，提醒同步更新测试。

## 项目结构

```text
expense_tracker/
  __main__.py       # python -m expense_tracker 入口
  cli.py            # 命令行参数和输出
  core.py           # 金额校验、JSON 存储和月度汇总
tests/
  test_tracker.py   # 正常功能与已知 bug 测试
pyproject.toml      # 包和命令行入口配置
```

本工具用于本地单用户学习演示，暂不提供多进程并发写入协调。

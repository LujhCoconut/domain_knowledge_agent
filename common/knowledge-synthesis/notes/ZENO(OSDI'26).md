# ZENO(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-huang-wenxuan.pdf
- **全称**: Accelerating Confidential Databases with Crypto-free Mappings
- **系统名**: ZENO
- **作者**: Wenxuan Huang, Zhanbo Wang, Mingyu Li (ISCAS, CAS)
- **类型**: 论文-系统 (database + confidential computing + security)
- **一句话 TL;DR**: 机密数据库 (CDB) 的核心瓶颈是每次跨 TEE 域调用需要 2 次解密 + 1 次加密（~6500 cycles），导致分析查询延迟最高比明文数据库慢 79.5×。ZENO 的核心洞察是**混淆了"间接寻址"和"保护"**——指针需要的是轻量级间接寻址（不是加密），数据需要的是加密保护（加密但不改变身份）。ZENO 将两者解耦：crypto-free mappings 在 DBMS 中维护数据独立的标识符（FID, plaintext-agnostic），仅在 TEE 内安全映射到明文秘密。TPC-H 加速 ARM S-EL2 **53.1×**、x86 TDX **94.7×**（vs HEDB）。已集成进 GaussDB。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **ZENO** | Crypto-free CDB 设计——将指针间接寻址与数据保护解耦 |
| **CDB** (Confidential Database) | 在不可信云环境中使用 TEE 对敏感数据进行安全查询的数据库 |
| **TEE** (Trusted Execution Environment) | ARM S-EL2、Intel TDX 等硬件安全域——仅安全关键操作在其中执行 |
| **Crypto-free mapping** | 维护数据独立的标识符（FID），在 TEE 内部映射到明文秘密——无需在映射层加密 |
| **FID** (Fixed Identifier) | 数据独立标识符——不随数据值变化，用于外部间接寻址 |
| **HEDB** | 基线 CDB 系统（对比目标） |
| **Split architecture** | 现代 CDB 的设计：仅安全关键操作符在 TEE 内执行，其余在普通 DBMS 中——管理友好但代价高昂 |

## 背景与动机

### 问题
- 机密数据库 (CDB) 使用 TEE 在不可信云上安全查询敏感数据
- 现代 CDB 的 split 架构（仅安全关键操作在 TEE 内，其余在普通 DBMS）使其可以被数据库管理员维护
- 但这种架构带来致命性能瓶颈：**每次跨 TEE 域的 RPC 调用**需要：
  - 数据离开 TEE → 加密 (~5000 cycles)
  - 数据进入 TEE → 解密 (~1500 cycles)
  - 总开销 ~6500 cycles，分析查询延迟最高达明文数据库的 **79.5×**

### 核心洞察
> "当前设计混淆了间接寻址和保护"——加密了两个东西：(1) 数据本身（应该加密），(2) 指针和标识符（不应该加密——它们只需要轻量级间接寻址，不需要保护机密性）。

ZENO 将两者解耦：
- **数据保护**: 加密数据值（不变）
- **间接寻址**: 使用 crypto-free 映射——维护数据独立的 FID 在 DBMS 中，仅在 TEE 内安全映射到明文秘密

这样可以消除 pointer dereference 路径上的加密/解密开销——而不影响数据安全性。

## 方案介绍

### Crypto-free Mapping 设计

1. **FID (Fixed Identifier)**: 数据独立标识符——不随数据值变化。存储在普通 DBMS 中，无需加密。
2. **Mapping store in TEE**: FID → plaintext secret 的映射仅在 TEE 内部维护——外部无法逆向映射。
3. **External synchrony**: 仅需 FID 可映射到明文值——反向映射（明文→FID）无需维护。简化了映射存储的一致性要求。
4. **Indirection without crypto**: 指针 dereference 路径全程无需加密/解密——FID 已经是 plaintext-safe 的间接寻址层。

### 安全性保证

- FID 不代表数据内容的任何信息——是数据独立的标识符
- 攻击者可以知道 FID 但无法从中推断明文值
- 数据加密仍然在 TEE 边界强制执行——ZENO 只去除了**指针层的加密**，不是数据层的

## 证据与评估

| 指标 | 结果 |
|------|------|
| TPC-H on ARM S-EL2 | **53.1×** 加速 vs HEDB |
| TPC-H on x86 TDX | **94.7×** 加速 vs HEDB |
| 基线退化 | 明文数据库分析查询延迟最高 **79.5×** |
| 生产集成 | 已集成进入 GaussDB |
| 工作负载 | TPC-C、TPC-H、真实工业负载 |

## 整体评估

### 真正的新颖性

1. **首次识别出 CDB 中"间接寻址"和"保护"被混淆了**——这是一个架构级别的洞察，不是简单的优化
2. **Crypto-free mapping** 是一个新的抽象——不是消除加密（数据仍需加密），而是将间接寻址层从加密中分离出来
3. **在 ARM S-EL2 和 x86 TDX 两个不同 TEE 平台上验证**——证明方法不限于单一硬件

### 可复用启发

- "不要加密指针"是一个广泛适用的原则——任何需要跨信任边界间接寻址的系统（不仅是 CDB，还包括 secure ML、federated analytics）都可以受益
- FID 作为数据独立标识符的抽象超越了 CDB——适用于任何"外部索引+安全存储"的场景
- "区分保护数据 vs 保护索引"是安全系统架构中的核心设计决策

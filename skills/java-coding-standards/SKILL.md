---
name: java-coding-standards
description: Java coding standards for Spring Boot services: naming, immutability, Optional usage, streams, exceptions, generics, and project layout.
---

# Java 编码规范

适用于 Spring Boot 服务的可读、可维护的 Java (8+) 代码规范。

## 核心原则

- 清晰优先于巧妙
- 默认不可变；最小化共享可变状态
- 快速失败，抛出有意义的异常
- 一致的命名和包结构

## 命名规范

```java
// ✅ 类名：PascalCase
public class MarketService {}
public class Money {}

// ✅ 方法/字段：camelCase
private final MarketRepository marketRepository;
public Market findBySlug(String slug) {}

// ✅ 常量：UPPER_SNAKE_CASE
private static final int MAX_PAGE_SIZE = 100;
```

## 不可变性

```java
// ✅ DTO 优先使用 final 字段和构建器模式
public class MarketDto {
    private final Long id;
    private final String name;
    private final MarketStatus status;

    private MarketDto(Long id, String name, MarketStatus status) {
        this.id = id;
        this.name = name;
        this.status = status;
    }

    public static MarketDto of(Long id, String name, MarketStatus status) {
        return new MarketDto(id, name, status);
    }

    // 仅提供 Getter，不提供 Setter
    public Long getId() { return id; }
    public String getName() { return name; }
    public MarketStatus getStatus() { return status; }
}

// 或使用 Lombok 简化代码
@Data
@Builder
@AllArgsConstructor
public class MarketDto {
    private final Long id;
    private final String name;
    private final MarketStatus status;
}

// 对于领域实体
public class Market {
  private final Long id;
  private final String name;
  // 仅 getter，无 setter
}
```

## Optional 使用规范

```java
// ✅ 从 find* 方法返回 Optional
Optional<Market> market = marketRepository.findBySlug(slug);

// ✅ 优先使用 map/flatMap 而非 get()
return market
    .map(MarketResponse::from)
    .orElseThrow(() -> new EntityNotFoundException("Market not found"));
```

### Optional 与异常的选择场景

| 场景 | 返回类型 | 原因 |
|------|----------|------|
| 根据 ID 在仓库中查找 | `Optional<T>` | 实体可能不存在，这是正常情况 |
| 根据唯一业务键获取 | `Optional<T>` | 键可能无效，属于正常流程 |
| 获取必需配置值 | `T` (抛异常) | 缺少配置是系统错误 |
| 解析用户输入 | `Optional<T>` | 无效输入是预期情况，不是错误 |
| 查找子项 | `Optional<T>` | 子项可能不存在 |

```java
// ✅ 正确：当"未找到"是有效业务结果时使用 Optional
@GetMapping("/markets/{slug}")
public ResponseEntity<MarketResponse> getBySlug(@PathVariable String slug) {
    return marketRepository.findBySlug(slug)
        .map(this::toResponse)
        .map(ResponseEntity::ok)
        .orElse(ResponseEntity.notFound().build());
}

// ✅ 正确：当"未找到"表示业务错误时抛出异常
@Transactional
public void submitBet(@NotNull Long marketId, @NotNull BigDecimal amount) {
    Market market = marketRepository.findById(marketId)
        .orElseThrow(() -> new MarketNotFoundException(marketId)); // 必须存在

    if (market.getStatus() != MarketStatus.ACTIVE) {
        throw new IllegalStateException("Market is not active");
    }
    // ...
}
```

## Stream 最佳实践

```java
// ✅ 使用 Stream 进行转换，保持管道简短
List<String> names = markets.stream()
    .map(Market::name)
    .filter(Objects::nonNull)
    .collect(Collectors.toList());

// ❌ 避免复杂的嵌套 Stream；为清晰起见优先使用循环
```

## 异常处理

- 对领域错误使用非受检异常；用上下文包装技术异常
- 创建领域特定异常（如 `MarketNotFoundException`）
- 避免广泛捕获 `catch (Exception ex)`，除非集中重新抛出/记录日志

```java
throw new MarketNotFoundException(slug);
```

## 泛型和类型安全

- 避免原始类型；声明泛型参数
- 优先使用有界泛型用于可复用工具类

```java
public <T extends Identifiable> Map<Long, T> indexById(Collection<T> items) { ... }
```

## 项目结构 (Maven/Gradle)

```
src/main/java/com/example/app/
  config/
  controller/
  service/
  repository/
  domain/
  dto/
  util/
src/main/resources/
  application.yml
src/test/java/... (结构与 main 对应)
```

## 格式和风格

- 统一使用 4 空格缩进（项目标准）
- 每个文件一个公共顶级类型
- 保持方法简短专注；提取辅助方法
- 成员排序：常量、字段、构造器、公共方法、保护方法、私有方法

## 并发和线程安全

Spring Boot 应用本质上是多线程的（Web 请求线程池）。遵循以下指南：

```java
// ✅ 正确：避免静态可变状态
// 错误：共享的可变静态字段
private static final Map<String, CacheEntry> CACHE = new HashMap<>();

// 正确：使用线程安全的并发集合或依赖注入
private final ConcurrentHashMap<String, CacheEntry> cache;

@Service
@RequiredArgsConstructor
public class CacheManager {
    private final ConcurrentHashMap<String, CacheEntry> cache;
}

// ✅ 正确：无状态服务默认线程安全
@Service
public class MarketService {
    private final MarketRepository marketRepository;
    private final PriceOracleClient priceOracle;

    @Transactional
    public Market createMarket(CreateMarketRequest request) {
        // 所有状态通过参数传递或每次调用时重新获取
        Market market = new Market(request.name());
        return marketRepository.save(market);
    }
}

// ✅ 正确：对单个可变值使用 AtomicReference
@Service
public class ConfigService {
    private final AtomicReference<Config> currentConfig = new AtomicReference<>();

    public void updateConfig(Config newConfig) {
        currentConfig.set(newConfig);
    }

    public Config getConfig() {
        return currentConfig.get();
    }
}

// ✅ 正确：对临界区使用 synchronized 块（很少需要）
@Service
public class IdGenerator {
    private long sequence = 0;

    public synchronized long nextId() {
        return sequence++;
    }
}

// ❌ 错误：非线程安全的单例状态
@Service
public class BadCounterService {
    private int counter = 0;

    public void increment() {
        counter++; // 竞态条件！非线程安全
    }
}

// ✅ 正确：替代方案 1 - AtomicLong
@Service
public class GoodCounterService {
    private final AtomicLong counter = new AtomicLong();

    public void increment() {
        counter.incrementAndGet();
    }
}

// ✅ 正确：替代方案 2 - 基于数据库的计数器
@Repository
public interface CounterRepository extends JpaRepository<Counter, Long> {
}

// ✅ 正确：使用 @Async 进行后台任务（需要 @EnableAsync）
@Async
public CompletableFuture<Void> sendNotificationEmail(User user) {
    emailService.send(user.getEmail(), "Welcome!");
    return CompletableFuture.completedFuture(null);
}

// ✅ 正确：使用 CompletableFuture 进行并行操作
public CompletableFuture<MarketResult> calculateMarketOdds(Market market) {
    CompletableFuture<BookmakerOdds> oddsFuture = fetchBookmakerOdds(market);
    CompletableFuture<MarketSentiment> sentimentFuture = fetchSentiment(market);

    return oddsFuture.thenCombine(sentimentFuture, MarketResult::combine);
}
```

### 并发规则

| 规则 | 说明 |
|------|------|
| **优先无状态服务** | Spring bean 默认单例；避免实例可变状态 |
| **静态可变状态有害** | 永不使用静态可变字段；使用依赖注入替代 |
| **使用并发集合** | 对共享数据使用 `ConcurrentHashMap`、`CopyOnWriteArrayList` |
| **原子类型** | 对简单可变值使用 `AtomicReference`、`AtomicLong` |
| **@Async 用于后台** | 将即发即忘任务卸载到单独线程 |
| **CompletableFuture** | 用于组合异步操作和并行执行 |

## JSON 序列化

Spring Boot 默认使用 Jackson。遵循以下模式以保持一致的 API 响应：

```java
// ✅ 正确：一致地格式化日期
public class MarketResponse {
    private Long id;
    private String name;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX")
    private Instant createdAt;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    private LocalDate endDate;

    // Getters and setters
}

// 或使用 Lombok
@Data
@JsonPropertyOrder({"id", "name", "createdAt", "endDate"})
public class MarketResponse {
    private Long id;
    private String name;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX")
    private Instant createdAt;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    private LocalDate endDate;
}

// ✅ 正确：自定义属性名称
public class UserProfile {
    @JsonProperty("user_id")
    private Long id;

    @JsonProperty("display_name")
    private String name;

    @JsonIgnore
    private String internalId;  // 永不序列化

    // Getters and setters
}

// ✅ 正确：一致地处理 null 值
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonInclude(JsonInclude.Include.NON_EMPTY)
public class PaginatedResponse<T> {
    private List<T> items;

    @JsonProperty("has_more")
    private Boolean hasMore;

    // Getters and setters
}

// ✅ 正确：根据上下文控制可见性
public class Account {
    private Long id;
    private String username;

    @JsonProperty(access = JsonProperty.Access.READ_ONLY)
    private BigDecimal balance;

    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private String passwordHash;

    // Getters and setters
}

// ✅ 正确：正确处理枚举
@JsonFormat(shape = JsonFormat.Shape.STRING)
public enum MarketStatus {
    ACTIVE,
    PAUSED,
    RESOLVED,
    CLOSED
}

// ✅ 正确：全局 Jackson 配置
@Configuration
public class JacksonConfig {
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer jacksonCustomizer() {
        return builder -> builder
            .serializationInclusion(JsonInclude.Include.NON_NULL)
            .failOnUnknownProperties(false)
            .timeZone(TimeZone.getTimeZone("UTC"))
            .modules(new JavaTimeModule());
    }
}
```

### JSON 序列化规则

| 规则 | 说明 |
|------|------|
| **日期格式化** | 使用 `@JsonFormat` 配合 ISO 8601 模式 |
| **属性命名** | 使用 `@JsonProperty` 指定 API 特定命名约定 |
| **空值处理** | 使用 `@JsonInclude(NON_NULL)` 排除 null 字段 |
| **敏感数据** | 使用 `@JsonIgnore` 或 `@JsonProperty(access = WRITE_ONLY)` |
| **枚举为字符串** | 使用 `@JsonFormat(shape = STRING)` 获得可读的枚举值 |
| **时区** | 序列化始终使用 UTC |
| **模块配置** | 注册 `JavaTimeModule` 用于 `Instant`、`LocalDate` 等 |

## 需避免的代码异味

- 长参数列表 → 使用 DTO/构建器
- 深层嵌套 → 提前返回
- 魔法数字 → 命名常量
- 静态可变状态 → 优先使用依赖注入
- 静默 catch 块 → 记录日志并处理或重新抛出

## 日志记录

```java
private static final Logger log = LoggerFactory.getLogger(MarketService.class);
log.info("fetch_market slug={}", slug);
log.error("failed_fetch_market slug={}", slug, ex);
```

## 空值处理

- 仅在不可避免时接受 `@Nullable`；否则使用 `@NonNull`
- 在输入上使用 Bean Validation（`@NotNull`、`@NotBlank`）

```java
// ✅ 正确：使用请求 DTO 和控制器处理的完整 Bean Validation
public class CreateMarketRequest {
    @NotBlank(message = "Name is required")
    @Size(min = 3, max = 200, message = "Name must be between 3 and 200 characters")
    private String name;

    @Size(max = 2000, message = "Description must not exceed 2000 characters")
    private String description;

    @NotNull(message = "End date is required")
    @Future(message = "End date must be in the future")
    private Instant endDate;

    @NotEmpty(message = "At least one category is required")
    private List<@NotBlank String> categories;

    // Getters and setters
}

// 或使用 Lombok
@Data
public class CreateMarketRequest {
    @NotBlank(message = "Name is required")
    @Size(min = 3, max = 200, message = "Name must be between 3 and 200 characters")
    private String name;

    @Size(max = 2000, message = "Description must not exceed 2000 characters")
    private String description;

    @NotNull(message = "End date is required")
    @Future(message = "End date must be in the future")
    private Instant endDate;

    @NotEmpty(message = "At least one category is required")
    private List<@NotBlank String> categories;
}

@RestController
@RequestMapping("/api/markets")
@Validated
public class MarketController {

    @PostMapping
    public ResponseEntity<MarketResponse> create(
        @RequestBody @Valid CreateMarketRequest request
    ) {
        Market created = marketService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(MarketResponse.from(created));
    }

    // 自定义验证错误处理
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<List<FieldError>> handleValidationExceptions(
        MethodArgumentNotValidException ex
    ) {
        List<FieldError> errors = ex.getBindingResult()
            .getFieldErrors()
            .stream()
            .map(error -> new FieldError(
                error.getField(),
                error.getRejectedValue(),
                error.getDefaultMessage()
            ))
            .collect(Collectors.toList());
        return ResponseEntity.badRequest().body(errors);
    }
}

// ✅ 正确：业务规则的服务级验证
@Service
public class MarketService {

    public Market create(@Valid CreateMarketRequest request) {
        // 额外的业务验证
        if (marketRepository.existsByName(request.getName())) {
            throw new DuplicateMarketNameException(request.getName());
        }

        if (Duration.between(Instant.now(), request.getEndDate()).toDays() < 1) {
            throw new ValidationException("Market must last at least 24 hours");
        }

        // ...
    }
}

// ✅ 正确：验证错误响应的 DTO
public class FieldError {
    private String field;
    private Object rejectedValue;
    private String message;

    // Constructor、getters、setters
}

// 或使用 Lombok
@Data
@AllArgsConstructor
public class FieldError {
    private String field;
    private Object rejectedValue;
    private String message;
}
```

## 测试期望

- JUnit 5 + AssertJ 用于流畅断言
- Mockito 用于模拟；尽可能避免部分模拟
- 优先确定性测试；无隐藏的 sleep

**切记**：保持代码有意图、有类型、可观察。除非证明必要，否则优先考虑可维护性而非微优化。
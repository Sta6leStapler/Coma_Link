# 接口契约（草案）

供前后端对齐的最小清单，当前以 `User` 相关为例。

## 统一返回结构
- 推荐格式：`{ "code": 0, "message": "ok", "data": { ... } }`
- 成功码：0 或 200；失败时 `code != 0/200`，`message` 带人类可读提示。
- Android 侧模型：`ApiResponse<T>(code: Int, message: String, data: T?)`

## 时间格式
- 统一使用 ISO 8601，含时区，例如 `2024-12-01T12:34:56Z` 或 `2024-12-01T21:34:56+09:00`。

## 鉴权
- 使用 `Authorization: Bearer <jwt>`。
- 建议提供 refresh token 端点：`POST /auth/refresh` 返回新的 access/refresh。

## 分页
- 建议 page/limit：`GET /users?page=1&limit=20`，返回字段 `page`, `limit`, `total`, `items`.
- 如果未来需要游标，可追加：`cursor`, `next_cursor`。

## 错误码约定
- 401 未授权：需要登录或 token 过期，返回 message 可提示重新登录。
- 403 禁止访问：权限不足。
- 422 参数校验失败：`message` 描述首个错误，必要时返回 `errors` 细节。
- 500 服务器内部错误：`message` 可返回通用提示。

## 用户接口示例
- Base URL 由 Product Flavors 注入 `BuildConfig.BASE_URL`
- `GET /user/me` → `ApiResponse<User>`
  - `User`: `{ id, name, email, avatarUrl?, updatedAt? }`

## 未来扩展
- 所有日期/时间字段沿用 ISO 8601
- 若接口返回列表，请保持字段命名统一（`items` / `page` / `limit` / `total`）


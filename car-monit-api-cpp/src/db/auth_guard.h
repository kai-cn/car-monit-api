#pragma once
// 数据库凭据守卫 + 认证失败熔断。
//
// 背景：configs/config.yaml 中的口令已改为 ${CM_PG_PASSWORD} 占位。若环境变量
// 缺失，旧实现会带着空口令去建连，产生一次“真实失败登录”，连续失败会触发
// openGauss 的 failed_login_attempts 并把账号锁死。这里把两道闸门前移：
//   1. 启动阶段校验口令，未配置/未展开时直接拒绝启动，不发起任何网络连接；
//   2. 运行期一旦出现认证类错误（28P01 / 28000），进程内停止自动重建连接。
//
// 熔断器提供可注入的连接工厂（Connector），便于单元测试断言“未发起连接”与
// “只尝试一次后熔断”，不依赖真实数据库。
#include <functional>
#include <mutex>
#include <string>

namespace cm::db {

// 口令校验结果。problem 为空表示通过。
struct CredentialCheck {
  bool ok = false;
  std::string problem;
};

// 未设置、全空白、或仍是未展开的 ${...} 占位时判定为不通过。
CredentialCheck check_password(const std::string& password);

// 认证失败熔断器（进程级单例）。
class AuthGuard {
public:
  enum class Outcome {
    Ok,         // 连接与认证成功
    AuthFailed, // 认证类错误（28P01 / 28000）
    OtherError, // 网络/协议等非认证错误
    Blocked,    // 熔断后拒绝发起连接（未产生任何网络 I/O）
  };

  // 可注入的连接工厂：返回本次尝试的结果。
  using Connector = std::function<Outcome()>;

  static AuthGuard& instance();

  // 以下三项仅供测试与运维使用。
  void reset();
  void set_connector(Connector connector);
  void clear_connector();

  // 认证失败后允许的重建连接次数，默认 0（= 关闭自动重连）。
  void set_max_attempts_after_failure(int n);

  bool blocked() const;
  int attempts() const;

  // 发起一次连接尝试；熔断后直接返回 Blocked，不调用 connector。
  Outcome attempt(const Connector& real);
  Outcome attempt();

  // 记录一次认证类失败并进入熔断。
  void mark_auth_failure(const std::string& sqlstate, const std::string& message);

private:
  AuthGuard() = default;

  mutable std::mutex mu_;
  bool blocked_ = false;
  int attempts_ = 0;
  int extra_after_failure_ = 0;
  int used_after_failure_ = 0;
  Connector injected_;
};

} // namespace cm::db

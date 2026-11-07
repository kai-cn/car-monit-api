#pragma once
// 纯 C++ 实现的摘要算法。仅用于 PostgreSQL SCRAM/MD5 认证与 RuoYi 的
// SecuritySHA1Utils，不用于任何对外加密场景。
#include <cstdint>
#include <string>
#include <vector>

namespace cm::crypto {

std::string md5_hex(const std::string& in);
std::string sha1_hex(const std::string& in);
std::string sha256_hex(const std::string& in);
std::vector<uint8_t> sha256_raw(const std::string& in);
std::vector<uint8_t> hmac_sha256(const std::vector<uint8_t>& key,
                                const std::vector<uint8_t>& data);
std::vector<uint8_t> pbkdf2_sha256(const std::string& password,
                                   const std::vector<uint8_t>& salt, int iterations,
                                   int dk_len);
std::string random_hex(std::size_t bytes);

} // namespace cm::crypto

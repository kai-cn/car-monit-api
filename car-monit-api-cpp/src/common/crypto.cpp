#include "common/crypto.h"

#include <cstring>
#include <random>

namespace cm::crypto {
namespace {

inline uint32_t rotl32(uint32_t x, int c) { return (x << c) | (x >> (32 - c)); }
inline uint32_t rotr32(uint32_t x, int c) { return (x >> c) | (x << (32 - c)); }

const uint32_t K256[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u,
    0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u,
    0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
    0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au,
    0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

void sha256_block(uint32_t h[8], const uint8_t* p) {
  uint32_t w[64];
  for (int i = 0; i < 16; ++i)
    w[i] = (uint32_t(p[i * 4]) << 24) | (uint32_t(p[i * 4 + 1]) << 16) |
           (uint32_t(p[i * 4 + 2]) << 8) | uint32_t(p[i * 4 + 3]);
  for (int i = 16; i < 64; ++i) {
    uint32_t s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
    uint32_t s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }
  uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
  for (int i = 0; i < 64; ++i) {
    uint32_t S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
    uint32_t ch = (e & f) ^ ((~e) & g);
    uint32_t t1 = hh + S1 + ch + K256[i] + w[i];
    uint32_t S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
    uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
    uint32_t t2 = S0 + maj;
    hh = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }
  h[0] += a; h[1] += b; h[2] += c; h[3] += d;
  h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

std::string hex_lower(const uint8_t* p, std::size_t n) {
  static const char* d = "0123456789abcdef";
  std::string out;
  out.reserve(n * 2);
  for (std::size_t i = 0; i < n; ++i) {
    out.push_back(d[p[i] >> 4]);
    out.push_back(d[p[i] & 0xF]);
  }
  return out;
}

void md5_block(uint32_t s[4], const uint8_t* p) {
  static const uint32_t T[64] = {
      0xd76aa478u, 0xe8c7b756u, 0x242070dbu, 0xc1bdceeeu, 0xf57c0fafu, 0x4787c62au,
      0xa8304613u, 0xfd469501u, 0x698098d8u, 0x8b44f7afu, 0xffff5bb1u, 0x895cd7beu,
      0x6b901122u, 0xfd987193u, 0xa679438eu, 0x49b40821u, 0xf61e2562u, 0xc040b340u,
      0x265e5a51u, 0xe9b6c7aau, 0xd62f105du, 0x02441453u, 0xd8a1e681u, 0xe7d3fbc8u,
      0x21e1cde6u, 0xc33707d6u, 0xf4d50d87u, 0x455a14edu, 0xa9e3e905u, 0xfcefa3f8u,
      0x676f02d9u, 0x8d2a4c8au, 0xfffa3942u, 0x8771f681u, 0x6d9d6122u, 0xfde5380cu,
      0xa4beea44u, 0x4bdecfa9u, 0xf6bb4b60u, 0xbebfbc70u, 0x289b7ec6u, 0xeaa127fau,
      0xd4ef3085u, 0x04881d05u, 0xd9d4d039u, 0xe6db99e5u, 0x1fa27cf8u, 0xc4ac5665u,
      0xf4292244u, 0x432aff97u, 0xab9423a7u, 0xfc93a039u, 0x655b59c3u, 0x8f0ccc92u,
      0xffeff47du, 0x85845dd1u, 0x6fa87e4fu, 0xfe2ce6e0u, 0xa3014314u, 0x4e0811a1u,
      0xf7537e82u, 0xbd3af235u, 0x2ad7d2bbu, 0xeb86d391u};
  static const int R[64] = {7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
                            5, 9,  14, 20, 5, 9,  14, 20, 5, 9,  14, 20, 5, 9,  14, 20,
                            4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
                            6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21};
  uint32_t a = s[0], b = s[1], c = s[2], d = s[3];
  uint32_t m[16];
  // MD5 按小端解析消息字（RFC 1321）。
  for (int i = 0; i < 16; ++i)
    m[i] = uint32_t(p[i * 4]) | (uint32_t(p[i * 4 + 1]) << 8) |
           (uint32_t(p[i * 4 + 2]) << 16) | (uint32_t(p[i * 4 + 3]) << 24);
  for (int i = 0; i < 64; ++i) {
    uint32_t f, g;
    if (i < 16) {
      f = (b & c) | ((~b) & d);
      g = uint32_t(i);
    } else if (i < 32) {
      f = (d & b) | ((~d) & c);
      g = uint32_t((5 * i + 1) % 16);
    } else if (i < 48) {
      f = b ^ c ^ d;
      g = uint32_t((3 * i + 5) % 16);
    } else {
      f = c ^ (b | (~d));
      g = uint32_t((7 * i) % 16);
    }
    uint32_t tmp = d;
    d = c;
    c = b;
    b = b + rotl32(a + f + T[i] + m[g], R[i]);
    a = tmp;
  }
  s[0] += a; s[1] += b; s[2] += c; s[3] += d;
}

void sha1_block(uint32_t h[5], const uint8_t* p) {
  uint32_t w[80];
  for (int i = 0; i < 16; ++i)
    w[i] = (uint32_t(p[i * 4]) << 24) | (uint32_t(p[i * 4 + 1]) << 16) |
           (uint32_t(p[i * 4 + 2]) << 8) | uint32_t(p[i * 4 + 3]);
  for (int i = 16; i < 80; ++i)
    w[i] = rotl32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
  uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
  for (int i = 0; i < 80; ++i) {
    uint32_t f, k;
    if (i < 20) { f = (b & c) | ((~b) & d); k = 0x5A827999u; }
    else if (i < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1u; }
    else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDCu; }
    else { f = b ^ c ^ d; k = 0xCA62C1D6u; }
    uint32_t t = rotl32(a, 5) + f + e + k + w[i];
    e = d; d = c; c = rotl32(b, 30); b = a; a = t;
  }
  h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}

// 通用 Merkle–Damgård 填充：返回完整分块（不含长度字段时另行计算）。
std::vector<uint8_t> pad(const std::string& in, bool len64) {
  std::vector<uint8_t> msg(in.begin(), in.end());
  std::size_t bits = in.size() * 8;
  msg.push_back(0x80);
  std::size_t block = 64;
  while (msg.size() % block != (len64 ? 56 : 60)) msg.push_back(0);
  if (len64) {
    uint64_t b = uint64_t(bits);
    for (int i = 7; i >= 0; --i) msg.push_back(uint8_t((b >> (i * 8)) & 0xFF));
  } else {
    uint32_t b = uint32_t(bits);
    for (int i = 3; i >= 0; --i) msg.push_back(uint8_t((b >> (i * 8)) & 0xFF));
  }
  return msg;
}

} // namespace

std::string md5_hex(const std::string& in) {
  uint32_t s[4] = {0x67452301u, 0xefcdab89u, 0x98badcfeu, 0x10325476u};
  std::vector<uint8_t> m(in.begin(), in.end());
  uint64_t bits = uint64_t(in.size()) * 8;
  m.push_back(0x80);
  while (m.size() % 64 != 56) m.push_back(0);
  for (int i = 0; i < 8; ++i) m.push_back(uint8_t((bits >> (i * 8)) & 0xFF));
  for (std::size_t i = 0; i < m.size(); i += 64) md5_block(s, m.data() + i);
  uint8_t out[16];
  for (int i = 0; i < 4; ++i) {
    out[i * 4] = uint8_t(s[i]);
    out[i * 4 + 1] = uint8_t(s[i] >> 8);
    out[i * 4 + 2] = uint8_t(s[i] >> 16);
    out[i * 4 + 3] = uint8_t(s[i] >> 24);
  }
  return hex_lower(out, 16);
}

std::string sha1_hex(const std::string& in) {
  uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
  auto m = pad(in, true);
  for (std::size_t i = 0; i < m.size(); i += 64) sha1_block(h, m.data() + i);
  uint8_t out[20];
  for (int i = 0; i < 5; ++i) {
    out[i * 4] = uint8_t(h[i] >> 24);
    out[i * 4 + 1] = uint8_t(h[i] >> 16);
    out[i * 4 + 2] = uint8_t(h[i] >> 8);
    out[i * 4 + 3] = uint8_t(h[i]);
  }
  return hex_lower(out, 20);
}

std::string sha256_hex(const std::string& in) {
  auto raw = sha256_raw(in);
  return hex_lower(raw.data(), raw.size());
}

std::vector<uint8_t> sha256_raw(const std::string& in) {
  uint32_t h[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                   0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
  auto m = pad(in, true);
  for (std::size_t i = 0; i < m.size(); i += 64) sha256_block(h, m.data() + i);
  std::vector<uint8_t> out(32);
  for (int i = 0; i < 8; ++i) {
    out[i * 4] = uint8_t(h[i] >> 24);
    out[i * 4 + 1] = uint8_t(h[i] >> 16);
    out[i * 4 + 2] = uint8_t(h[i] >> 8);
    out[i * 4 + 3] = uint8_t(h[i]);
  }
  return out;
}

std::vector<uint8_t> hmac_sha256(const std::vector<uint8_t>& key,
                                 const std::vector<uint8_t>& data) {
  std::vector<uint8_t> k = key;
  if (k.size() > 64) k = sha256_raw(std::string(k.begin(), k.end()));
  k.resize(64, 0);
  std::vector<uint8_t> ipad(64), opad(64);
  for (int i = 0; i < 64; ++i) {
    ipad[i] = uint8_t(k[i] ^ 0x36);
    opad[i] = uint8_t(k[i] ^ 0x5c);
  }
  std::vector<uint8_t> inner = ipad;
  inner.insert(inner.end(), data.begin(), data.end());
  auto ih = sha256_raw(std::string(inner.begin(), inner.end()));
  std::vector<uint8_t> outer = opad;
  outer.insert(outer.end(), ih.begin(), ih.end());
  return sha256_raw(std::string(outer.begin(), outer.end()));
}

std::vector<uint8_t> pbkdf2_sha256(const std::string& password,
                                   const std::vector<uint8_t>& salt, int iterations,
                                   int dk_len) {
  std::vector<uint8_t> key(password.begin(), password.end());
  std::vector<uint8_t> out;
  for (int block = 1; int(out.size()) < dk_len; ++block) {
    std::vector<uint8_t> u = salt;
    // PBKDF2 的块序号按 4 字节大端拼接（RFC 8018 5.2）。
    u.push_back(uint8_t((block >> 24) & 0xFF));
    u.push_back(uint8_t((block >> 16) & 0xFF));
    u.push_back(uint8_t((block >> 8) & 0xFF));
    u.push_back(uint8_t(block & 0xFF));
    auto first = hmac_sha256(key, u);
    std::vector<uint8_t> acc = first;
    for (int i = 1; i < iterations; ++i) {
      auto next = hmac_sha256(key, first);
      for (std::size_t j = 0; j < acc.size(); ++j) acc[j] ^= next[j];
      first = next;
    }
    out.insert(out.end(), acc.begin(), acc.end());
  }
  out.resize(std::size_t(dk_len));
  return out;
}

std::string random_hex(std::size_t bytes) {
  std::random_device rd;
  std::vector<uint8_t> buf(bytes);
  for (auto& b : buf) b = uint8_t(rd() & 0xFF);
  return hex_lower(buf.data(), buf.size());
}

} // namespace cm::crypto

package com.ruoyi.base.agent.core;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 会话 id 归一化（{@link RedisAgentSessionStore#safe}）的回归用例。
 *
 * <p>为什么单独测这个静态方法：它同时决定 Redis List 的 Key 与索引 ZSet 的 member，
 * 一旦不满足下面几条不变式，症状都是"线上才看得见"的数据问题
 * （两个会话串历史、列表点进去是空的），而不是启动就报错。</p>
 */
class RedisAgentSessionStoreTest {

    @Test
    @DisplayName("归一化必须幂等：列表返回的 id 再传回来要得到同一个 Key")
    void safeIsIdempotent() {
        // 长度 > 64 才会走"截断 + 哈希"分支，也正是最容易写错的分支
        String longId = "x".repeat(80);
        String once = RedisAgentSessionStore.safe(longId);
        String twice = RedisAgentSessionStore.safe(once);
        // 曾用 '~' 作为截断分隔符：它不在白名单里，第二次归一化会被替换成 '_'，
        // 于是"历史列表里的会话点进去查不到消息"。
        assertEquals(once, twice, "二次归一化必须原样返回");
        // 边界：64 不动、65 才截断，否则刚好 64 的合法 id 会被无谓地改写
        String at64 = "z".repeat(64);
        String at65 = "z".repeat(65);
        assertEquals(at64, RedisAgentSessionStore.safe(at64), "64 字符应原样保留");
        assertNotEquals(at65, RedisAgentSessionStore.safe(at65), "65 字符应被截断改写");
    }

    @Test
    @DisplayName("归一化结果长度受控，且不同输入不会撞到同一个 Key")
    void safeKeepsLengthBoundedAndDistinct() {
        String a = RedisAgentSessionStore.safe("y".repeat(80) + "-a");
        String b = RedisAgentSessionStore.safe("y".repeat(80) + "-b");
        assertAll(
                () -> assertTrue(a.length() <= 64, "超过 64 字符会撑长 Redis Key：" + a.length()),
                () -> assertNotEquals(a, b, "截断后必须靠哈希后缀区分，否则两个会话共用一份历史")
        );
    }

    @Test
    @DisplayName("非法字符被清洗，空值落到默认槽位")
    void safeSanitizesIllegalCharacters() {
        // 斜杠/空格/花括号都是危险字符：'/' 是 AgentScope 状态布局的分隔符，
        // '{}' 会与 Redis 集群 hash tag 冲突，空白会让 Key 难以排查。
        assertEquals("a_b_c", RedisAgentSessionStore.safe("a/b c"));
        assertEquals("default", RedisAgentSessionStore.safe("   "));
        assertEquals("default", RedisAgentSessionStore.safe(null));
        Set<String> uniq = new HashSet<>();
        uniq.add(RedisAgentSessionStore.safe("a b"));
        uniq.add(RedisAgentSessionStore.safe("a_b"));
        // 这两个输入清洗后必然相同（白名单里没有空格），这是已知且可接受的折叠；
        // 断言出来是为了让后来者知道"不要指望用空格区分会话"。
        assertEquals(1, uniq.size());
    }
}

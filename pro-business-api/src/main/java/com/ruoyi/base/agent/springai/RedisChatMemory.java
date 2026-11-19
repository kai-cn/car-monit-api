package com.ruoyi.base.agent.springai;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.config.AgentProperties;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.MessageType;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Redis 会话记忆。
 *
 * <p>只持久化 user/assistant 的<b>文本</b>，不持久化工具调用原始报文：
 * 多轮对话需要的是语义上下文，工具大结果留在当轮，避免上下文膨胀与敏感数据长期留存。</p>
 *
 * <p>Key：{@code agent:chat:{tenant}:{user}:{sessionId}}，List，TTL 与会话一致。</p>
 */
@Slf4j
public class RedisChatMemory implements ChatMemory {

    private final StringRedisTemplate redis;
    private final AgentProperties properties;

    public RedisChatMemory(StringRedisTemplate redis, AgentProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    @Override
    public void add(String conversationId, List<Message> messages) {
        if (messages == null || messages.isEmpty()) {
            return;
        }
        List<String> values = new ArrayList<>();
        for (Message message : messages) {
            StoredMessage stored = toStored(message);
            if (stored != null) {
                values.add(JSON.toJSONString(stored));
            }
        }
        if (values.isEmpty()) {
            return;
        }
        String key = key(conversationId);
        int window = Math.max(2, properties.getHistoryWindow() * 2);
        try {
            redis.opsForList().rightPushAll(key, values);
            redis.opsForList().trim(key, -window, -1);
            redis.expire(key, properties.getSessionTtl());
        } catch (RuntimeException e) {
            log.warn("[Agent记忆] Redis 写入失败（不影响本轮对话）: {}", e.getMessage());
        }
    }

    @Override
    public List<Message> get(String conversationId) {
        String key = key(conversationId);
        int window = Math.max(2, properties.getHistoryWindow() * 2);
        try {
            List<String> values = redis.opsForList().range(key, -window, -1);
            if (values == null || values.isEmpty()) {
                return Collections.emptyList();
            }
            List<Message> messages = new ArrayList<>(values.size());
            for (String value : values) {
                try {
                    StoredMessage stored = JSON.parseObject(value, StoredMessage.class);
                    Message message = fromStored(stored);
                    if (message != null) {
                        messages.add(message);
                    }
                } catch (Exception ignored) {
                    // 单条损坏不影响整体上下文
                }
            }
            return messages;
        } catch (RuntimeException e) {
            log.warn("[Agent记忆] Redis 读取失败，按无历史处理: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    @Override
    public void clear(String conversationId) {
        try {
            redis.delete(key(conversationId));
        } catch (RuntimeException e) {
            log.warn("[Agent记忆] Redis 删除失败: {}", e.getMessage());
        }
    }

    private String key(String conversationId) {
        return properties.getKeyPrefix() + ":chat:" + conversationId;
    }

    private static StoredMessage toStored(Message message) {
        if (message == null || message.getMessageType() == MessageType.TOOL) {
            return null;
        }
        String text = message.getText();
        if (text == null || text.isBlank()) {
            return null;
        }
        StoredMessage stored = new StoredMessage();
        stored.setRole(message.getMessageType().getValue());
        stored.setText(text.length() > 4000 ? text.substring(0, 4000) : text);
        return stored;
    }

    private static Message fromStored(StoredMessage stored) {
        if (stored == null || stored.getText() == null || stored.getRole() == null) {
            return null;
        }
        return switch (stored.getRole()) {
            case "user" -> new UserMessage(stored.getText());
            case "assistant" -> new AssistantMessage(stored.getText());
            case "system" -> new SystemMessage(stored.getText());
            default -> null;
        };
    }

    @Data
    public static class StoredMessage {
        private String role;
        private String text;
    }
}

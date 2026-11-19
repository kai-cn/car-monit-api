package com.ruoyi.base.agent.springai;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.definition.DefaultToolDefinition;
import org.springframework.ai.tool.definition.ToolDefinition;
import org.springframework.ai.tool.metadata.ToolMetadata;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 基于手写 JSON Schema 的 ToolCallback。
 *
 * <p>不使用 {@code @Tool} 反射生成 schema，原因：</p>
 * <ul>
 *   <li>参数名/描述与 AgentScope 分支、Spec 文档保持完全一致（snake_case）；</li>
 *   <li>schema 是显式常量，可做启动期校验与契约测试；</li>
 *   <li>不依赖反射与参数名保留，GraalVM native-image 更友好。</li>
 * </ul>
 */
public class JsonToolCallback implements ToolCallback {

    @FunctionalInterface
    public interface Handler {
        String handle(Map<String, Object> arguments, ToolContext context);
    }

    private static final ToolMetadata METADATA = ToolMetadata.builder().returnDirect(false).build();

    private final AgentToolCatalog.ToolSpec spec;
    private final ToolDefinition definition;
    private final Handler handler;

    public JsonToolCallback(AgentToolCatalog.ToolSpec spec, Handler handler) {
        this.spec = spec;
        this.definition = DefaultToolDefinition.builder()
                .name(spec.name())
                .description(spec.description())
                .inputSchema(spec.inputSchema())
                .build();
        this.handler = handler;
    }

    @Override
    public ToolDefinition getToolDefinition() {
        return definition;
    }

    @Override
    public ToolMetadata getToolMetadata() {
        return METADATA;
    }

    @Override
    public String call(String toolInput) {
        return call(toolInput, null);
    }

    @Override
    public String call(String toolInput, ToolContext toolContext) {
        Map<String, Object> args = parse(toolInput);
        return handler.handle(args, toolContext);
    }

    public AgentToolCatalog.ToolSpec spec() {
        return spec;
    }

    private static Map<String, Object> parse(String toolInput) {
        if (toolInput == null || toolInput.isBlank()) {
            return new LinkedHashMap<>();
        }
        try {
            JSONObject json = JSON.parseObject(toolInput);
            return json == null ? new LinkedHashMap<>() : new LinkedHashMap<>(json);
        } catch (Exception e) {
            throw new IllegalArgumentException("工具参数不是合法 JSON: " + e.getMessage());
        }
    }

    static String json(Object value) {
        return JSON.toJSONString(value);
    }
}

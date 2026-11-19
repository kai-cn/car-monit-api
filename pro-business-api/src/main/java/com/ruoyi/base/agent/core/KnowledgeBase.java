package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 轻量知识库：启动时加载 classpath 下的 Markdown（表结构、指标口径、FAQ），
 * 按标题/段落切块，使用中英文混合的 BM25-lite 检索。
 *
 * <p>选择“进程内词法检索 + 工具化调用”而不是强依赖向量库：
 * 知识条目是人工维护的少量高价值文档（几十到几百块），词法检索足够；
 * 不引入额外中间件，且每次检索都有明确出处（source），便于审计与纠错。
 * 需要语义检索时，可在 {@code search_knowledge} 工具内部替换为向量实现，
 * 对上层的工具契约不变。</p>
 */
@Slf4j
@Component
public class KnowledgeBase {

    private static final Pattern HEADING = Pattern.compile("^(#{1,3})\\s+(.*)$");
    private static final int MAX_CHUNK_CHARS = 900;

    private final AgentProperties properties;
    private final List<Chunk> chunks = new ArrayList<>();
    private final Map<String, Integer> documentFrequency = new HashMap<>();

    public KnowledgeBase(AgentProperties properties) {
        this.properties = properties;
    }

    @PostConstruct
    public void load() {
        PathMatchingResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();
        try {
            Resource[] resources = resolver.getResources(properties.getKnowledgeLocation());
            for (Resource resource : resources) {
                loadResource(resource);
            }
            for (Chunk chunk : chunks) {
                for (String term : chunk.terms.keySet()) {
                    documentFrequency.merge(term, 1, Integer::sum);
                }
            }
            log.info("[Agent知识库] 加载完成：{} 个文档块，{} 个词项", chunks.size(), documentFrequency.size());
        } catch (Exception e) {
            log.warn("[Agent知识库] 加载失败，search_knowledge 将返回空结果: {}", e.getMessage());
        }
    }

    private void loadResource(Resource resource) throws Exception {
        String source = resource.getFilename() == null ? "unknown" : resource.getFilename();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            String title = source;
            StringBuilder body = new StringBuilder();
            while ((line = reader.readLine()) != null) {
                Matcher m = HEADING.matcher(line.trim());
                if (m.matches()) {
                    flush(source, title, body);
                    title = m.group(2).trim();
                } else {
                    body.append(line).append('\n');
                }
            }
            flush(source, title, body);
        }
    }

    private void flush(String source, String title, StringBuilder body) {
        String text = body.toString().trim();
        body.setLength(0);
        if (text.length() < 20) {
            return;
        }
        // 超长段落按空行/句号切分，避免单块过大挤占上下文。
        for (String part : split(text, MAX_CHUNK_CHARS)) {
            if (part.length() >= 20) {
                chunks.add(new Chunk("kb-" + (chunks.size() + 1), title, source, part, tokenize(part)));
            }
        }
    }

    private static List<String> split(String text, int max) {
        List<String> parts = new ArrayList<>();
        if (text.length() <= max) {
            parts.add(text);
            return parts;
        }
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(text.length(), start + max);
            if (end < text.length()) {
                int cut = text.lastIndexOf('\n', end);
                if (cut <= start) {
                    cut = text.lastIndexOf('。', end);
                }
                if (cut > start) {
                    end = cut + 1;
                }
            }
            parts.add(text.substring(start, end).trim());
            start = end;
        }
        return parts;
    }

    public List<KnowledgeHit> search(String query, int topK) {
        if (query == null || query.isBlank() || chunks.isEmpty()) {
            return Collections.emptyList();
        }
        Map<String, Integer> queryTerms = tokenize(query);
        if (queryTerms.isEmpty()) {
            return Collections.emptyList();
        }
        double n = chunks.size();
        List<KnowledgeHit> scored = new ArrayList<>();
        for (Chunk chunk : chunks) {
            double score = 0;
            for (String term : queryTerms.keySet()) {
                int tf = chunk.terms.getOrDefault(term, 0);
                if (tf == 0) {
                    continue;
                }
                int df = documentFrequency.getOrDefault(term, 0);
                double idf = Math.log((n + 1) / (df + 1)) + 1;
                score += (tf * idf) / Math.sqrt(chunk.length);
                if (chunk.title.toLowerCase().contains(term)) {
                    score += idf * 0.5;
                }
            }
            if (score > 0) {
                scored.add(new KnowledgeHit(chunk.id, chunk.title, chunk.source, chunk.content,
                        Math.round(score * 1000d) / 1000d));
            }
        }
        scored.sort((a, b) -> Double.compare(b.score(), a.score()));
        return scored.size() <= topK ? scored : new ArrayList<>(scored.subList(0, topK));
    }

    /** 中文二元组 + 英文/数字词，足够支撑小规模知识库的召回。 */
    static Map<String, Integer> tokenize(String text) {
        Map<String, Integer> terms = new HashMap<>();
        if (text == null) {
            return terms;
        }
        String lower = text.toLowerCase();
        Matcher ascii = Pattern.compile("[a-z0-9_]{2,}").matcher(lower);
        while (ascii.find()) {
            terms.merge(ascii.group(), 1, Integer::sum);
        }
        Matcher cjk = Pattern.compile("[\\u4e00-\\u9fa5]+").matcher(lower);
        while (cjk.find()) {
            String run = cjk.group();
            for (int i = 0; i < run.length(); i++) {
                if (i + 1 < run.length()) {
                    terms.merge(run.substring(i, i + 2), 1, Integer::sum);
                }
                if (run.length() == 1) {
                    terms.merge(run, 1, Integer::sum);
                }
            }
            // 完整词组对精确命中的帮助很大（如“收费站”“轨迹拟合”）。
            if (run.length() <= 6) {
                terms.merge(run, 2, Integer::sum);
            }
        }
        return terms;
    }

    public int size() {
        return chunks.size();
    }

    private static final class Chunk {
        private final String id;
        private final String title;
        private final String source;
        private final String content;
        private final Map<String, Integer> terms;
        private final int length;

        private Chunk(String id, String title, String source, String content, Map<String, Integer> terms) {
            this.id = id;
            this.title = title;
            this.source = source;
            this.content = content;
            this.terms = terms;
            this.length = Math.max(1, terms.values().stream().mapToInt(Integer::intValue).sum());
        }
    }

    /** 命中的知识块与出处，直接作为工具结果返回给模型。 */
    public record KnowledgeHit(String id, String title, String source, String content, double score) {
    }
}

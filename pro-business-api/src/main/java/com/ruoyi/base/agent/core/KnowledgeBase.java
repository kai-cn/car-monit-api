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
 * 按标题/段落切块，使用中英文混合的**简化 TF-IDF** 检索（见下方"与 BM25 的区别"）。
 *
 * <p>选择“进程内词法检索 + 工具化调用”而不是强依赖向量库：
 * 知识条目是人工维护的少量高价值文档（几十到几百块），词法检索足够；
 * 不引入额外中间件，且每次检索都有明确出处（source），便于审计与纠错。
 * 需要语义检索时，可在 {@code search_knowledge} 工具内部替换为向量实现，
 * 对上层的工具契约不变。</p>
 *
 * <h2>AI 概念：RAG（检索增强生成）</h2>
 * <p>大模型不知道"我们平台的"指标口径、表名、字段含义——这些存在私有文档里。
 * 两种做法：① 把所有文档塞进提示词（贵、且有上下文长度上限）；② 先把文档切块建索引，
 * 用户提问时只检索最相关的几块塞进提示词。后者就是 RAG。</p>
 *
 * <h2>为什么用词法检索而不是向量检索</h2>
 * <p>词法检索（TF-IDF 家族）按"词频 × 逆文档频率 ÷ 文档长度"打分：词频越高越相关、
 * 出现在越多文档里的词权重越低、再按文档长度归一。对本场景（术语固定、条目少、要求"可解释"）
 * 它比向量更合适：命中原因肉眼可查、无需 embedding 服务、零额外延迟。这里还做了中文二元切分
 * （"门架交易" → "门架"/"架交"/"交易"），因为中文没有空格分词。</p>
 *
 * <p><b>与 BM25 的区别</b>：标准 BM25 有词频饱和（{@code k1}）与文档长度归一（{@code b}）两个参数，
 * 长文档不会因为词多就无限加分；本实现是 {@code score = tf × idf / sqrt(len)}，
 * 属于"够用的近似"——条目规模在几百块量级时二者排序差异很小，但<b>不是</b>严格 BM25，
 * 若将来文档量级上升、需要调参，可在这里替换为真正的 BM25 或向量检索。</p>
 *
 * <p>【Java 9+ 不可变集合】{@link List#of} / {@link Map#of} 创建的是不可变集合，
 * 内部做了紧凑存储；但注意它们<b>不接受 null 元素</b>，且 {@code of()} 重载到 10 个元素，
 * 更多要用 {@code of(...)} 的可变参数版本或 {@code copyOf}。</p>
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

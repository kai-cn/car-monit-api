package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class KnowledgeBaseTest {

    private KnowledgeBase knowledgeBase;

    @BeforeEach
    void setUp() {
        AgentProperties properties = new AgentProperties();
        knowledgeBase = new KnowledgeBase(properties);
        knowledgeBase.load();
    }

    @Test
    void loadsBundledKnowledge() {
        assertTrue(knowledgeBase.size() >= 10, "知识块数量过少: " + knowledgeBase.size());
    }

    @Test
    void findsTableAndMetricDocs() {
        List<KnowledgeBase.KnowledgeHit> hits = knowledgeBase.search("plate_norm 车牌归一化字段", 3);
        assertFalse(hits.isEmpty());
        assertTrue(hits.get(0).content().toLowerCase().contains("plate_norm")
                        || hits.get(0).content().contains("车牌"),
                "unexpected top hit: " + hits.get(0).title());

        List<KnowledgeBase.KnowledgeHit> metrics = knowledgeBase.search("逃费金额口径", 3);
        assertFalse(metrics.isEmpty());
    }

    @Test
    void returnsEmptyForUnknownTopic() {
        assertTrue(knowledgeBase.search("量子纠缠", 3).isEmpty());
    }
}

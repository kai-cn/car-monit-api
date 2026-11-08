package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.base.service.IOdsSzdnTollService;
import com.ruoyi.base.service.IOdsYhglVBaseOrgService;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * P1-1/P1-2 自证：收费表 org/road/toll 维度必须翻译为门架编码集合，
 * 而不是直接下推并不存在的 orgcode/roadcode/tollcode 字段。
 */
class DimensionCodeResolverTest {

    private DimensionCodeResolver resolverWith(List<OdsSzdnGantry> gantries) {
        IOdsSzdnGantryService gantryService = mock(IOdsSzdnGantryService.class);
        when(gantryService.getGantryRedis()).thenReturn(gantries);
        return new DimensionCodeResolver(
                mock(IOdsYhglVBaseOrgService.class),
                mock(IOdsSzdnSectionService.class),
                gantryService,
                mock(IOdsSzdnTollService.class));
    }

    @Test
    void translatesOrgAndRoadToGantryCodes() {
        DimensionCodeResolver resolver = resolverWith(Arrays.asList(
                gantry("G001", "030000011", "R001", "T001"),
                gantry("G002", "030000011", "R002", "T002"),
                gantry("G003", "030000099", "R001", "T003")));

        Map<String, List<String>> codes = new LinkedHashMap<>();
        codes.put("orgcode", Arrays.asList("030000011"));
        codes.put("roadcode", Arrays.asList("R001"));

        assertTrue(resolver.translateFeeDimensions(codes));
        assertEquals(Arrays.asList("G001"), codes.get("gantrycode"));
        assertFalse(codes.containsKey("orgcode"));
        assertFalse(codes.containsKey("roadcode"));
    }

    @Test
    void intersectsExplicitGantryFilter() {
        DimensionCodeResolver resolver = resolverWith(Arrays.asList(
                gantry("G001", "030000011", "R001", "T001"),
                gantry("G002", "030000011", "R002", "T002")));

        Map<String, List<String>> codes = new LinkedHashMap<>();
        codes.put("orgcode", Arrays.asList("030000011"));
        codes.put("gantrycode", Arrays.asList("G002"));

        assertTrue(resolver.translateFeeDimensions(codes));
        assertEquals(Arrays.asList("G002"), codes.get("gantrycode"));
    }

    @Test
    void returnsNoMatchWhenDimensionHasNoGantry() {
        DimensionCodeResolver resolver = resolverWith(Arrays.asList(
                gantry("G001", "030000011", "R001", "T001")));

        Map<String, List<String>> codes = new LinkedHashMap<>();
        codes.put("orgcode", Arrays.asList("030000999"));

        assertFalse(resolver.translateFeeDimensions(codes));
    }

    @Test
    void keepsCodesUntouchedWhenNoFeeDimensionGiven() {
        DimensionCodeResolver resolver = resolverWith(new ArrayList<>());

        Map<String, List<String>> codes = new LinkedHashMap<>();
        codes.put("sectioncode", Arrays.asList("S001"));

        assertTrue(resolver.translateFeeDimensions(codes));
        assertEquals(Arrays.asList("S001"), codes.get("sectioncode"));
        assertFalse(codes.containsKey("gantrycode"));
    }

    private OdsSzdnGantry gantry(String code, String org, String road, String toll) {
        OdsSzdnGantry g = new OdsSzdnGantry();
        g.setGantryCode(code);
        g.setOrgCode(org);
        g.setRoadCode(road);
        g.setTollCode(toll);
        return g;
    }
}

package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.plate.PlateNumberParser;
import org.elasticsearch.client.RestHighLevelClient;
import org.junit.jupiter.api.Test;

import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * P2/P1-1 自证：未知维度键显式 400；收费维度无匹配时不打 ES、直接返回空。
 */
class TrafficSearchServiceDimensionTest {

    private TrafficSearchService service(DimensionCodeResolver resolver) {
        return new TrafficSearchService(
                mock(RestHighLevelClient.class),
                mock(TrafficEsIndexService.class),
                mock(PlateNumberParser.class),
                new TrafficV3Properties(),
                resolver);
    }

    private TrafficSearchRequest request(TrafficTable table) {
        long now = System.currentTimeMillis();
        TrafficSearchRequest req = new TrafficSearchRequest();
        req.setTable(table);
        req.setStartMillis(now - 60_000L);
        req.setEndMillis(now);
        return req;
    }

    @Test
    void rejectsUnknownDimensionField() {
        TrafficSearchRequest req = request(TrafficTable.SNAPSHOT);
        req.getDimensionCodes().put("bogus", Arrays.asList("x"));

        TrafficQueryException error = assertThrows(TrafficQueryException.class,
                () -> service(mock(DimensionCodeResolver.class)).search(req));
        assertEquals(400, error.getCode());
    }

    @Test
    void returnsEmptyWithoutCallingEsWhenFeeDimensionHasNoGantry() {
        DimensionCodeResolver resolver = mock(DimensionCodeResolver.class);
        when(resolver.translateFeeDimensions(any())).thenReturn(false);

        TrafficSearchRequest req = request(TrafficTable.FEE);
        req.getDimensionCodes().put("orgcode", Arrays.asList("030000999"));

        TrafficSearchResult result = service(resolver).search(req);
        assertEquals(0, result.getTotal());
        assertEquals(0, result.getRows().size());
        assertEquals(false, result.isHasMore());
    }
}

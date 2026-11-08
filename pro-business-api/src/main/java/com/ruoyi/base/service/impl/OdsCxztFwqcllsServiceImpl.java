package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsCxztFwqclls;
import com.ruoyi.base.mapper.OdsCxztFwqcllsMapper;
import com.ruoyi.base.service.IOdsCxztFwqcllsService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 服务区车辆流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-10-20
 */
@Service
public class OdsCxztFwqcllsServiceImpl extends ServiceImpl<OdsCxztFwqcllsMapper, OdsCxztFwqclls> implements IOdsCxztFwqcllsService {

    @Autowired
    private OdsCxztFwqcllsMapper odsCxztFwqcllsMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询服务区车辆流水
     *
     * @param bigId 服务区车辆流水ID
     * @return 服务区车辆流水
     */
    @Override
    public OdsCxztFwqclls selectOdsCxztFwqcllsById(Long bigId) {
        return odsCxztFwqcllsMapper.selectOdsCxztFwqcllsById(bigId);
    }

    /**
     * 查询服务区车辆流水列表
     *
     * @param odsCxztFwqclls 服务区车辆流水
     * @return 服务区车辆流水
     */
    @Override
    public List<OdsCxztFwqclls> selectOdsCxztFwqcllsList(OdsCxztFwqclls odsCxztFwqclls) {
        return odsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(odsCxztFwqclls);
    }

    /**
     * 单批查询的 UUID 数量上限
     */
    private static final int UUID_BATCH_SIZE = 1000;

    /**
     * 详情缓存时长（分钟）
     */
    private static final int DETAIL_CACHE_MINUTES = 10;

    @Override
    public Map<String, OdsCxztFwqclls> selectOdsCxztFwqcllsByQueryUuids(String queryUuids) {
        Map<String, OdsCxztFwqclls> map = new HashMap<>();
        if (CommonUtil.isBlank(queryUuids)) {
            return map;
        }
        List<String> uuidList = Arrays.stream(queryUuids.split(","))
                .filter(CommonUtil::isNotBlank)
                .distinct()
                .collect(Collectors.toList());
        if (uuidList.isEmpty()) {
            return map;
        }

        List<String> missList = new ArrayList<>();
        for (String uuid : uuidList) {
            String key = Constants.DATE_SERVICE_AREA_CAPTURE + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsCxztFwqclls) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            OdsCxztFwqclls querybo = new OdsCxztFwqclls();
            querybo.setUuidList(chunk);
            List<OdsCxztFwqclls> list = odsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(querybo);
            Map<String, OdsCxztFwqclls> loaded = new HashMap<>();
            if (list != null) {
                for (OdsCxztFwqclls row : list) {
                    if (row.getDatauuid() != null) {
                        loaded.putIfAbsent(row.getDatauuid(), row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsCxztFwqclls row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_SERVICE_AREA_CAPTURE + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }
}

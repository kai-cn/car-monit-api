package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsCxztFwqclls;
import com.ruoyi.base.mapper.OdsCxztFwqcllsMapper;
import com.ruoyi.base.service.IOdsCxztFwqcllsService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
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

    @Override
    public Map<String, OdsCxztFwqclls> selectOdsCxztFwqcllsByQueryUuids(String queryUuids) {
        Map<String, OdsCxztFwqclls> map = new HashMap<>();
        if (StringUtils.isNotBlank(queryUuids)) {
            List<String> uuidList = Arrays.stream(queryUuids.split(",")).collect(Collectors.toList());
            for (String uuid : uuidList) {
                // redis查找
                String key = Constants.SERVICE_AREA_CAPTURE + uuid;
                Object obj = redisCache.getCacheObject(key);
                if (null != obj) {
                    map.put(uuid, (OdsCxztFwqclls) obj);
                } else {
                    OdsCxztFwqclls querybo = new OdsCxztFwqclls();
                    querybo.setDatauuid(uuid);
                    List<OdsCxztFwqclls> list = odsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(querybo);
                    if (null!=list && list.size() > 0) {
                        map.put(uuid, list.get(0));
                        redisCache.setCacheObject(key, list.get(0));
                    }
                }
            }
        }
        return map;
    }
}

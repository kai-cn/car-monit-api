package com.ruoyi.common.config;

import ma.glasnost.orika.Converter;
import ma.glasnost.orika.Mapper;
import ma.glasnost.orika.MapperFactory;
import ma.glasnost.orika.impl.ConfigurableMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 实体类与dto转换的映射
 *
 * @author 黄君
 * @date 2020年5月20日
 */
@Component
public class OrikaMapperConfig extends ConfigurableMapper {

    @Autowired(required = false)
    private List<Mapper> mappers;

    @Autowired(required = false)
    private List<Converter> converters;

    @Override
    protected void configure(MapperFactory factory) {
        super.configure(factory);
        if (mappers != null) {
            mappers.forEach(mapper -> factory.classMap(mapper.getAType(), mapper.getBType()).byDefault().customize(mapper).register());
        }
        if (converters != null) {
            converters.forEach(converter -> factory.getConverterFactory().registerConverter(converter));
        }
    }
}

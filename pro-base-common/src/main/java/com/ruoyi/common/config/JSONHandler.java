package com.ruoyi.common.config;

import com.fasterxml.jackson.annotation.JsonInclude;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;

import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

/**
 * Jackson 3 版本的 JSON TypeHandler。
 *
 * <p>迁移要点：Jackson 3 的 ObjectMapper 不可变构建（JsonMapper.builder()），
 * 读写失败抛非受检的 {@code JacksonException}，因此不再声明 IOException。</p>
 *
 * @Description:
 * @Author HuangJun
 * @Date 2024/8/30 16:56
 * @Return
 */
@Slf4j
@MappedTypes({Object.class})
@MappedJdbcTypes(JdbcType.VARCHAR)
public class JSONHandler<T extends Object> extends BaseTypeHandler<T> {

    private static final ObjectMapper mapper = JsonMapper.builder()
            .disable(StreamReadFeature.INCLUDE_SOURCE_IN_LOCATION)
            .changeDefaultPropertyInclusion(inclusion -> inclusion.withValueInclusion(JsonInclude.Include.NON_NULL))
            .build();

    private Class<T> clazz;

    public JSONHandler(Class<T> clazz) {
        if (clazz == null) {
            throw new NullPointerException("Type argument cannot be null");
        }
        this.clazz = clazz;
    }

    /**
     * object转json string
     */
    private String toJSON(T object) {
        try {
            String string = mapper.writeValueAsString(object);
            log.info(">>>> json handler string:{} <<<<", string);
            return string;
        } catch (Exception e) {
            log.error(">>>> covert object to json string failed, error message:{} <<<<", e.getMessage());
        }
        return null;
    }

    /**
     * json转object
     */
    private T toObject(String json) {
        if (json != null && !json.isEmpty()) {
            return mapper.readValue(json, clazz);
        }
        return null;
    }

    @Override
    public void setNonNullParameter(PreparedStatement preparedStatement, int i, T t, JdbcType jdbcType) throws SQLException {
        try {
            preparedStatement.setString(i, toJSON(t));
        } catch (Exception e) {
            log.error(">>>> preparedStatement set string failed, error message:{} <<<<", e.getMessage());
        }
    }

    @Override
    public T getNullableResult(ResultSet resultSet, String s) throws SQLException {
        try {
            return toObject(resultSet.getString(s));
        } catch (Exception e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<", e.getMessage());
        }
        return null;
    }

    @Override
    public T getNullableResult(ResultSet resultSet, int i) throws SQLException {
        try {
            return toObject(resultSet.getString(i));
        } catch (Exception e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<", e.getMessage());
        }
        return null;
    }

    @Override
    public T getNullableResult(CallableStatement callableStatement, int i) throws SQLException {
        try {
            return toObject(callableStatement.getString(i));
        } catch (Exception e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<", e.getMessage());
        }
        return null;
    }
}

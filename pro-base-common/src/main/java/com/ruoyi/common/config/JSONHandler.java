package com.ruoyi.common.config;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;

import java.io.IOException;
import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/8/30 16:56
 * @Return
 */
@Slf4j
@MappedTypes({Object.class})
@MappedJdbcTypes(JdbcType.VARCHAR)
public class JSONHandler<T extends Object> extends BaseTypeHandler<T> {

    private static final ObjectMapper mapper = new ObjectMapper();

    private Class<T> clazz;

    static {
        mapper.configure(JsonParser.Feature.ALLOW_MISSING_VALUES, false);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
    }

    public JSONHandler(Class<T> clazz) {
        if (clazz == null) {
            throw new NullPointerException("Type argument cannot be null");
        }
        this.clazz = clazz;
    }

    /**
     * object转json string
     * @param object
     * @return
     */
    private String toJSON(T object) {
        try {
            String string = mapper.writeValueAsString(object);
            log.info(">>>> json handler string:{} <<<<",string);
            return string;
        } catch (Exception e) {
            log.error(">>>> covert object to json string failed, error message: <<<<",e.getMessage());
        }
        return null;
    }

    /**
     * json转object
     * @param json
     * @param clazz
     * @return
     * @throws IOException
     */
    private T toObject(String json, Class<T> clazz) throws IOException {
        if (json != null && json != "") {
            return mapper.readValue(json,clazz);
        }
        return null;
    }

    @Override
    public void setNonNullParameter(PreparedStatement preparedStatement, int i, T t, JdbcType jdbcType) throws SQLException {
        try {
            preparedStatement.setString(i,toJSON(t));
        } catch (Exception e) {
            log.error(">>>> preparedStatement set string failed, error message:{} <<<<",e.getMessage());
        }
    }

    @Override
    public T getNullableResult(ResultSet resultSet, String s) throws SQLException {
        try {
            return toObject(resultSet.getString(s), clazz);
        } catch (IOException e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<",e.getMessage());
        }
        return null;
    }

    @Override
    public T getNullableResult(ResultSet resultSet, int i) throws SQLException {
        try {
            return toObject(resultSet.getString(i), clazz);
        } catch (IOException e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<",e.getMessage());
        }
        return null;
    }

    @Override
    public T getNullableResult(CallableStatement callableStatement, int i) throws SQLException {
        try {
            return toObject(callableStatement.getString(i), clazz);
        } catch (IOException e) {
            log.error(">>>> convert json string to object failed, error message:{} <<<<",e.getMessage());
        }
        return null;
    }
}

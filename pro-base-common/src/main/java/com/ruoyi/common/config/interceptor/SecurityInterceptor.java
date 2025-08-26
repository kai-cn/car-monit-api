/*
package com.ruoyi.common.config.interceptor;

import com.alibaba.fastjson.JSON;
import com.ruoyi.common.config.annotation.PermissionAnon;
import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.common.constant.Constants;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.ModelAndView;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.Objects;

@Slf4j
@Component
public class SecurityInterceptor implements HandlerInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(SecurityInterceptor.class);
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        boolean permissionValid = this.hasPermission(request, response, handler);
        if(!permissionValid){
            // 如果没有权限 则抛401
            logger.error("Responding with unauthorized error. Message:{}, url:{}", "没有API访问权限", request.getRequestURI());
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.setCharacterEncoding("UTF-8");
            response.setContentType("application/json;charset=utf-8");
            Result result = new Result();
            result.setCode(HttpStatus.UNAUTHORIZED.value());
            result.setSuccess(false);
            result.setMessage("未授权访问：No Permission 401");
            response.getWriter().println(JSON.toJSONString(result));
            return false;
        }
        return true;
    }

    */
/**
     * 是否有权限
     *
     * @param handler
     * @return
     *//*

    private boolean hasPermission(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (handler instanceof HandlerMethod) {
            HandlerMethod handlerMethod = (HandlerMethod) handler;
            // 获取方法上的注解
            PermissionAnon permission = handlerMethod.getMethod().getAnnotation(PermissionAnon.class);
            // 如果方法上的注解为空 则获取类的注解
            if (permission == null) {
                permission = handlerMethod.getMethod().getDeclaringClass().getAnnotation(PermissionAnon.class);
            }
            // 如果标记了注解，则判断权限
            if (permission != null) {
                return true;
            }else{
                //判断请求头
                ValidHeader headerParamValid = handlerMethod.getMethodAnnotation(ValidHeader.class);
                if (headerParamValid != null) {
                    for (String headerName : headerParamValid.value()) {
                        String headerValue = request.getHeader(headerName);
                        if(Objects.equals("d-anno",headerName)){
                            if(headerValue == null || headerValue.isEmpty() || !Objects.equals(Constants.D_ANNO,headerValue)){
                                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                                response.setCharacterEncoding("UTF-8");
                                response.setContentType("application/json;charset=utf-8");
                                return false;
                            }
                        }else if(Objects.equals("d-cookie",headerName)){
                            if (headerValue == null || headerValue.isEmpty()) {
                                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                                response.setCharacterEncoding("UTF-8");
                                response.setContentType("application/json;charset=utf-8");
                                return false;
                            }
                        }
                    }
                }
            }
        }
        return true;
    }

    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response, Object handler, ModelAndView modelAndView) throws Exception {
        // TODO
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        // TODO
    }
}
*/

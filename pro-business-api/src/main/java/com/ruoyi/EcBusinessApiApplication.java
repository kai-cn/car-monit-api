package com.ruoyi;

import lombok.extern.slf4j.Slf4j;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;

import java.net.InetAddress;
import java.net.UnknownHostException;

@Slf4j
@SpringBootApplication
@MapperScan(value={"com.ruoyi.base.**.mapper*"})
public class EcBusinessApiApplication {

    public static void main(String[] args) throws UnknownHostException {
        ConfigurableApplicationContext application = SpringApplication.run(EcBusinessApiApplication.class, args);
        Environment env = application.getEnvironment();
        String ip = InetAddress.getLocalHost().getHostAddress();
        String port = env.getProperty("server.port");
        String path = env.getProperty("server.servlet.context-path");
        log.info("\n----------------------------------------------------------\n\t" +
                "Application ammeter-workorder is running! Access URLs:\n\t" +
                "Local: \t\thttp://localhost:" + port + path + "doc.html\n\t" +
                "External: \thttp://" + ip + ":" + port + path + "\n\t" +
                "Doc: \t\thttp://" + ip + ":" + port + path + "doc.html\n" +
                "----------------------------------------------------------");
    }
}

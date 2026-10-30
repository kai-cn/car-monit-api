package com.ruoyi.base.device;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 硬件设备数据上报模拟器
 *
 * 功能说明：
 * 1. 模拟门架抓拍、省界称重、收费站、服务区等设备
 * 2. 生成模拟数据并上报到Kafka
 * 3. 支持批量上报、延迟模拟等
 */
@Slf4j
@Component
public class DeviceDataSimulator {

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    private static final String KAFKA_TOPIC_RAW_DATA = "device-raw-data";

    // 模拟设备列表
    private static final List<DeviceInfo> DEVICES = Arrays.asList(
            new DeviceInfo("Gantry-001", "GANTRY", "京承高速", "朝阳区", 116.404, 39.915),
            new DeviceInfo("Gantry-002", "GANTRY", "京承高速", "顺义区", 116.653, 40.134),
            new DeviceInfo("Border-001", "BORDER_WEIGHING", "京冀界", "大兴区", 116.302, 39.732),
            new DeviceInfo("Station-001", "TOLL_STATION", "望京站", "朝阳区", 116.473, 39.983),
            new DeviceInfo("Station-002", "TOLL_STATION", "顺义站", "顺义区", 116.682, 40.137),
            new DeviceInfo("Service-001", "SERVICE_AREA", "顺义服务区", "顺义区", 116.632, 40.083)
    );

    // 模拟车牌号
    private static final List<String> PLATE_PREFIX = Arrays.asList(
            "京A", "京B", "京C", "京E", "京F", "京G", "京H", "京J", "京K", "京L"
    );

    // 随机数生成器
    private final ThreadLocalRandom random = ThreadLocalRandom.current();

    /**
     * 单条设备数据上报
     */
    public void simulateSingleReport() {
        // 随机选择一个设备
        DeviceInfo device = DEVICES.get(random.nextInt(DEVICES.size()));

        // 生成数据
        Object data = generateDeviceData(device);

        // 上报Kafka
        reportToKafka(device, data);
    }

    /**
     * 批量设备数据上报
     *
     * @param count 上报条数
     */
    public void simulateBatchReport(int count) {
        log.info("[设备模拟] 开始批量上报：count={}", count);

        for (int i = 0; i < count; i++) {
            simulateSingleReport();

            // 随机延迟0-100ms
            try {
                Thread.sleep(random.nextInt(100));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        log.info("[设备模拟] 批量上报完成");
    }

    /**
     * 根据设备类型生成对应数据
     */
    private Object generateDeviceData(DeviceInfo device) {
        switch (device.deviceType) {
            case "GANTRY":
                return generateGantryData(device);
            case "BORDER_WEIGHING":
                return generateBorderWeighingData(device);
            case "TOLL_STATION":
                return generateTollStationData(device);
            case "SERVICE_AREA":
                return generateServiceAreaData(device);
            default:
                return generateGantryData(device);
        }
    }

    /**
     * 生成门架抓拍数据
     *
     * 与项目中OdsRtSzdnSnapshotFlowAddcode表结构对应
     */
    private OdsRtSzdnSnapshotFlowAddcode generateGantryData(DeviceInfo device) {
        OdsRtSzdnSnapshotFlowAddcode data = new OdsRtSzdnSnapshotFlowAddcode();

        // 基础信息
        data.setBigId(UUID.randomUUID().toString().replace("-", ""));
        data.setDatasource("SIMULATED_GANTRY");
        data.setCameratype("HIGH_SPEED_CAMERA");
        data.setDeviceid(device.deviceId);

        // 门架信息
        data.setGantrycode(device.deviceId);
        data.setGantryname(device.roadName);
        data.setRoadcode("G101");
        data.setRoadname(device.roadName);
        data.setSectioncode("SEC-001");
        data.setSectionname(device.district + "段");

        // 经纬度
        data.setLon(new BigDecimal(device.lon));
        data.setLat(new BigDecimal(device.lat));

        // 车辆信息
        String plateNumber = generatePlateNumber();
        data.setPlatenumber(plateNumber);
        data.setPlatecolor(randomPlateColor());
        data.setPlatetypecode(random.nextBoolean() ? 1 : 2);
        data.setCartype(randomVehicleType());
        data.setCartypecode(random.nextInt(1, 10));

        // 时间信息
        Date captureTime = new Date();
        data.setSnapshottime(captureTime);
        data.setSnapshottimeunix(captureTime.getTime());
        data.setReceivedtime(new Date(captureTime.getTime() + random.nextInt(100, 500)));
        data.setLoadtime(new Date());

        // 图片信息
        String imagePath = "/images/" + formatDate(captureTime) + "/" + data.getBigId() + ".jpg";
        data.setSnappicturepath(imagePath);

        // 速度信息 (speed字段不存在, 已移除)

        return data;
    }

    /**
     * 生成省界称重数据
     */
    private Map<String, Object> generateBorderWeighingData(DeviceInfo device) {
        Map<String, Object> data = new HashMap<>();

        data.put("bigId", UUID.randomUUID().toString().replace("-", ""));
        data.put("deviceId", device.deviceId);
        data.put("deviceType", "BORDER_WEIGHING");
        data.put("plateNumber", generatePlateNumber());
        data.put("captureTime", new Date());
        data.put("vehicleWeight", random.nextDouble(1.0, 49.0));
        data.put("axleCount", random.nextInt(2, 7));
        data.put("overweight", random.nextBoolean());
        data.put("lon", device.lon);
        data.put("lat", device.lat);
        data.put("location", device.roadName);

        return data;
    }

    /**
     * 生成收费站数据
     */
    private Map<String, Object> generateTollStationData(DeviceInfo device) {
        Map<String, Object> data = new HashMap<>();

        data.put("bigId", UUID.randomUUID().toString().replace("-", ""));
        data.put("deviceId", device.deviceId);
        data.put("deviceType", "TOLL_STATION");
        data.put("plateNumber", generatePlateNumber());
        data.put("captureTime", new Date());
        data.put("direction", random.nextBoolean() ? "IN" : "OUT");
        data.put("laneId", "LANE-" + random.nextInt(1, 6));
        data.put("tollFee", random.nextDouble(5.0, 500.0));
        data.put("lon", device.lon);
        data.put("lat", device.lat);
        data.put("location", device.roadName);

        return data;
    }

    /**
     * 生成服务区数据
     */
    private Map<String, Object> generateServiceAreaData(DeviceInfo device) {
        Map<String, Object> data = new HashMap<>();

        data.put("bigId", UUID.randomUUID().toString().replace("-", ""));
        data.put("deviceId", device.deviceId);
        data.put("deviceType", "SERVICE_AREA");
        data.put("plateNumber", generatePlateNumber());
        data.put("captureTime", new Date());
        data.put("action", Arrays.asList("ENTER", "EXIT", "PARKING").get(random.nextInt(3)));
        data.put("lon", device.lon);
        data.put("lat", device.lat);
        data.put("location", device.roadName);

        return data;
    }

    /**
     * 上报数据到Kafka
     */
    private void reportToKafka(DeviceInfo device, Object data) {
        String key = device.deviceId + ":" + System.currentTimeMillis();
        String jsonData = JSON.toJSONString(data);

        log.debug("[设备上报] 类型={}, 设备={}, key={}",
                device.deviceType, device.deviceId, key);

        kafkaTemplate.send(KAFKA_TOPIC_RAW_DATA, key, data);
    }

    /**
     * 生成车牌号
     */
    private String generatePlateNumber() {
        String prefix = PLATE_PREFIX.get(random.nextInt(PLATE_PREFIX.size()));
        String suffix = String.valueOf(random.nextInt(10000, 99999));
        return prefix + suffix;
    }

    /**
     * 随机车牌颜色
     */
    private String randomPlateColor() {
        String[] colors = {"蓝", "黄", "绿", "白", "黑"};
        return colors[random.nextInt(colors.length)];
    }

    /**
     * 随机车辆类型
     */
    private String randomVehicleType() {
        String[] types = {"小型轿车", "大型客车", "货车", "危险品运输车"};
        return types[random.nextInt(types.length)];
    }

    /**
     * 格式化日期
     */
    private String formatDate(Date date) {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy/MM/dd");
        return sdf.format(date);
    }

    /**
     * 设备信息
     */
    @lombok.AllArgsConstructor
    @lombok.Data
    private static class DeviceInfo {
        String deviceId;
        String deviceType;
        String roadName;
        String district;
        double lon;
        double lat;
    }
}

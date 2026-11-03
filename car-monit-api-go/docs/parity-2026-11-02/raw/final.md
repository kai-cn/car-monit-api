| 用例 | 请求 | 判定 | Java | Go | 差异摘要 | 稳定 |
|---|---|---|---|---|---|---|
| bad-json-post | `POST /base/sysutil/changeTrailInfo` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| empty-post | `POST /base/sysutil/changeTrailInfo` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| trailing-slash | `GET /base/gantry/list/?pageSize=1` | STATUS | 200 | 404 | java=200 go=404 | 否(重试后一致) |
| feeGantry-filter-actualfeeclass | `GET /base/feeGantry/list?pageNum=1&pageSize=5&actualfeeclass=1` | NONDET | 200 | 200 | `rows[bigId="237"].id`(VALUE); `rows[bigId="269"].id`(VALUE); `rows[bigId="58"].id`(VALUE); `rows[bigId="59"].id`(VALUE); `rows[bigId="89"].id`(VALUE) | 是 |
| feeGantry-filter-axlecount | `GET /base/feeGantry/list?pageNum=1&pageSize=5&axlecount=6` | NONDET | 200 | 200 | `rows[bigId="237"].id`(VALUE); `rows[bigId="269"].id`(VALUE); `rows[bigId="317"].id`(VALUE); `rows[bigId="59"].id`(VALUE); `rows[bigId="89"].id`(VALUE) | 是 |
| feeGantry-filter-createtime | `GET /base/feeGantry/list?pageNum=1&pageSize=5&createtime=2024-11-11T10` | NONDET | 200 | 200 | `rows[bigId="4"].id`(VALUE); `rows[bigId="407"].id`(VALUE); `rows[bigId="420"].id`(VALUE); `rows[bigId="58"].id`(VALUE); `rows[bigId="59"].id`(VALUE) | 是 |
| feeGantry-filter-discountfee | `GET /base/feeGantry/list?pageNum=1&pageSize=5&discountfee=1388` | NONDET | 200 | 200 | `rows[bigId="271"].id`(VALUE); `rows[bigId="275"].id`(VALUE); `rows[bigId="327"].id`(VALUE); `rows[bigId="339"].id`(VALUE); `rows[bigId="59"].id`(VALUE) | 是 |
| feeGantry-full-set | `GET /base/feeGantry/list?pageNum=1&pageSize=200` | NONDET | 200 | 200 | `rows[bigId="100"].id`(VALUE); `rows[bigId="1006"].id`(VALUE); `rows[bigId="1020"].id`(VALUE); `rows[bigId="1036"].id`(VALUE); `rows[bigId="1062"].id`(VALUE); `rows[bigId="1087"].id`(VALUE) …共 200 项 | 是 |
| feeGantry-list-bigpagesize | `GET /base/feeGantry/list?pageNum=1&pageSize=5000` | NONDET | 200 | 200 | `rows[bigId="100"].id`(VALUE); `rows[bigId="1006"].id`(VALUE); `rows[bigId="1020"].id`(VALUE); `rows[bigId="1036"].id`(VALUE); `rows[bigId="1062"].id`(VALUE); `rows[bigId="1087"].id`(VALUE) …共 200 项 | 是 |
| feeGantry-list-default | `GET /base/feeGantry/list?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `rows[bigId="4"].id`(VALUE); `rows[bigId="407"].id`(VALUE); `rows[bigId="420"].id`(VALUE); `rows[bigId="58"].id`(VALUE); `rows[bigId="59"].id`(VALUE) | 是 |
| feeGantry-list-farpage | `GET /base/feeGantry/list?pageNum=99999&pageSize=5` | NONDET | 200 | 200 | `rows[bigId="3891"].id`(VALUE); `rows[bigId="4242"].id`(VALUE); `rows[bigId="4430"].id`(VALUE); `rows[bigId="4661"].id`(VALUE); `rows[bigId="4855"].id`(VALUE) | 是 |
| feeGantry-list-noargs | `GET /base/feeGantry/list` | NONDET | 200 | 200 | `rows[bigId="1103"].id`(VALUE); `rows[bigId="4"].id`(VALUE); `rows[bigId="407"].id`(VALUE); `rows[bigId="420"].id`(VALUE); `rows[bigId="423"].id`(VALUE); `rows[bigId="58"].id`(VALUE) …共 10 项 | 是 |
| feeGantry-list-order | `GET /base/feeGantry/list?pageNum=1&pageSize=5&orderByColumn=bigId&isAs` | NONDET | 200 | 200 | `rows[bigId="969"].id`(VALUE); `rows[bigId="978"].id`(VALUE); `rows[bigId="982"].id`(VALUE); `rows[bigId="984"].id`(VALUE); `rows[bigId="992"].id`(VALUE) | 是 |
| feeGantry-list-page2 | `GET /base/feeGantry/list?pageNum=2&pageSize=5` | NONDET | 200 | 200 | `rows[bigId="1103"].id`(VALUE); `rows[bigId="423"].id`(VALUE); `rows[bigId="795"].id`(VALUE); `rows[bigId="829"].id`(VALUE); `rows[bigId="984"].id`(VALUE) | 是 |
| feerecords-list-bigpagesize | `GET /base/feerecords/list?pageNum=1&pageSize=5000` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-default | `GET /base/feerecords/list?pageNum=1&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-farpage | `GET /base/feerecords/list?pageNum=99999&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-noargs | `GET /base/feerecords/list` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-order | `GET /base/feerecords/list?pageNum=1&pageSize=5&orderByColumn=bigId&isA` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-page2 | `GET /base/feerecords/list?pageNum=2&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-pagesize-1 | `GET /base/feerecords/list?pageNum=1&pageSize=-1` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-pagesize0 | `GET /base/feerecords/list?pageNum=1&pageSize=0` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-listToExport | `GET /base/feerecords/listToExport?pageNum=1&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-filter-agentPk | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&agentPk=1` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-filter-yxtzj | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&yxtzj=45L4479928780847000` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-info-miss | `GET /base/fwqjcxx/__no_such_id__` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| prog-feerecords | `GET /progressive/feerecords/list?startTime=2025-10-01+00%3A00%3A00&end` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| prog-trailfitting | `GET /progressive/trailfitting/list?startTime=2025-10-01+00%3A00%3A00&e` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| sfsjcxx-filter-agentPk | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&agentPk=d2c6df4afa7ff18d48` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| snapshotflow-filter-direction | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&direction=1` | NONDET | 200 | 200 | `rows[id="167f841b380a4d3489fc7d700b00b3df"]`(ONLY_JAVA); `rows[id="529815bc-b1e2-4f77-bbfe-a284c5cf0b83"]`(ONLY_GO); `rows[id="55ce40fab30147b296857374b52f8107"]`(ONLY_JAVA); `rows[id="627af51f1c744a4eae10c2b51774801a"]`(ONLY_JAVA); `rows[id="65e218ee-135b-4237-8190-c9759f59e224"]`(ONLY_GO); `rows[id="70df75ba-3932-4a06-b2f8-e7c153b6b28c"]`(ONLY_GO) …共 10 项 | 是 |
| snapshotflow-filter-gantryname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&gantryname=%E9%9F%B6%` | NONDET | 200 | 200 | `rows[id="3260da1d-e22c-41eb-82ee-7b9295c86096"]`(ONLY_GO); `rows[id="3e33f78777634afb810f671c40bb9450"]`(ONLY_JAVA); `rows[id="4d4521902c7045008e12fa4fe70484ce"]`(ONLY_JAVA); `rows[id="5e9845cc-98c4-42de-8644-4fa88b834a8c"]`(ONLY_GO); `rows[id="5f715c526abb49e086c5d0452b9d1664"]`(ONLY_JAVA); `rows[id="7944ba3f85bc40fc838524fe4591e40a"]`(ONLY_JAVA) …共 10 项 | 是 |
| snapshotflow-filter-roadname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&roadname=%E5%A4%A7%E5` | NONDET | 200 | 200 | `rows[id="25549be9ad7b4d8e95ff6216ac3c8e4c"]`(ONLY_JAVA); `rows[id="5331e5f370b542b799772a2b4340cc5e"]`(ONLY_JAVA); `rows[id="66449381b04248d38f6a843647f73a13"]`(ONLY_JAVA); `rows[id="79620032-e64d-4c43-bdde-f23eb34e6a2d"]`(ONLY_GO); `rows[id="7e5092e1-9801-4616-8e70-eb11efcafb74"]`(ONLY_GO); `rows[id="944e4344-c812-44f0-821e-2fcc5382be7b"]`(ONLY_GO) …共 10 项 | 是 |
| snapshotflow-filter-sectionname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&sectionname=%E6%B3%B0` | NONDET | 200 | 200 | `rows[id="043b9e34-a42f-48c0-a7f8-0fc6051ece17"]`(ONLY_GO); `rows[id="1a9eafee91774f4e97b2eb617298095b"]`(ONLY_JAVA); `rows[id="304b09ce-c987-4596-b8c7-903a0a18faf5"]`(ONLY_GO); `rows[id="4f167596-bc02-4a67-ad40-c5bec2c65054"]`(ONLY_GO); `rows[id="50e93a675d6c45dbba16eefb71ff3f1e"]`(ONLY_JAVA); `rows[id="513ae697-d84b-46fa-b8c0-5a6830e0ed8f"]`(ONLY_GO) …共 10 项 | 是 |
| snapshotflow-full-set | `GET /base/snapshotflow/list?pageNum=1&pageSize=251` | NONDET | 200 | 200 | `rows[id="002919bce2de4c23a4ddcfffd4a548cf"]`(ONLY_JAVA); `rows[id="007e80e1-6fa1-4da2-8dbd-ccb659ad64a7"]`(ONLY_GO); `rows[id="00cbc3d2-b013-4353-8904-0fe8ede74d57"]`(ONLY_GO); `rows[id="0171a6cbc54c4b1daf072247bb875b6a"]`(ONLY_JAVA); `rows[id="01b01d94-d411-4dc0-9b65-ec8ae1d30668"]`(ONLY_GO); `rows[id="038ea91d4e554f73a1b43b7473e5e39b"]`(ONLY_JAVA) …共 502 项 | 是 |
| snapshotflow-list-bigpagesize | `GET /base/snapshotflow/list?pageNum=1&pageSize=5000` | NONDET | 200 | 200 | `rows[id="00b812e3-e10f-458f-ad85-91f3ac75816e"]`(ONLY_GO); `rows[id="00ee112bed1540d6bed171cf2147ce2e"]`(ONLY_JAVA); `rows[id="0161c199-e629-4284-98b7-b54b1f30c72e"]`(ONLY_GO); `rows[id="01b169d6-a877-4e3b-afa2-37c329e9cb56"]`(ONLY_GO); `rows[id="01ba45e5-d4b3-4f69-a1d8-00eea981f0da"]`(ONLY_GO); `rows[id="02418cd717da4f169327ebdafe338c64"]`(ONLY_JAVA) …共 502 项 | 是 |
| snapshotflow-list-default | `GET /base/snapshotflow/list?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `rows[id="045ea6bcd5ca41bdb2c0b0647924a08a"]`(ONLY_JAVA); `rows[id="3521b93a581e4d21af9f5ed62bc7554d"]`(ONLY_JAVA); `rows[id="356b6d02-8689-4c57-bf16-94f13605769f"]`(ONLY_GO); `rows[id="3a4be9ce7ab74257ac813c02591f525c"]`(ONLY_JAVA); `rows[id="3aba8ea4-bf12-451d-b503-1db3eaac3ccd"]`(ONLY_GO); `rows[id="6bdebb76-3710-49ee-a760-4728fae7df20"]`(ONLY_GO) …共 10 项 | 是 |
| snapshotflow-list-farpage | `GET /base/snapshotflow/list?pageNum=99999&pageSize=5` | NONDET | 200 | 200 | `rows[id="2adc0893832b4914b9e897065c4183ab"]`(ONLY_JAVA); `rows[id="9031d53c-096f-497e-becf-62e0904c9bfc"]`(ONLY_GO) | 是 |
| snapshotflow-list-noargs | `GET /base/snapshotflow/list` | NONDET | 200 | 200 | `rows[id="1732190164444634a92cc04d8ff72878"]`(ONLY_JAVA); `rows[id="1e5c686e-514d-4de6-8e95-cb53d288a815"]`(ONLY_GO); `rows[id="243da25be4a145cb8fea1d0bf7b71686"]`(ONLY_JAVA); `rows[id="2b3fe910-8b7d-478a-87df-37f286d5dd38"]`(ONLY_GO); `rows[id="3d1d6870-b6a4-4f6c-96bc-049a0dc9afad"]`(ONLY_GO); `rows[id="3d4ef86f-1a33-4e07-b668-cbc75d3a58fc"]`(ONLY_GO) …共 20 项 | 是 |
| snapshotflow-list-order | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&orderByColumn=id&isAs` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| snapshotflow-list-page2 | `GET /base/snapshotflow/list?pageNum=2&pageSize=5` | NONDET | 200 | 200 | `rows[id="1eda6f0b-ba28-4055-8a86-0007b9cf74eb"]`(ONLY_GO); `rows[id="5f419bbc-9c91-4f1e-bfb8-609e9301d0b6"]`(ONLY_GO); `rows[id="607d190ebe274c5e96a52f204c926ecc"]`(ONLY_JAVA); `rows[id="93d8f61f80a1460e81b5f2a15646c53d"]`(ONLY_JAVA); `rows[id="b84cccfc-21c9-4b1b-b795-a8b11750dbfd"]`(ONLY_GO); `rows[id="ca3921f4d47347bfa55c8949747fcf8f"]`(ONLY_JAVA) …共 10 项 | 是 |
| snapshotflow-listToExport | `GET /base/snapshotflow/listToExport?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `[id="17091772acfc4bc4b351df742e8654bc"]`(ONLY_JAVA); `[id="38b657c5254347d7a7b40801843e9f37"]`(ONLY_JAVA); `[id="7a3a4150dc8847e8bac379a68ba7c7ca"]`(ONLY_JAVA); `[id="8eeddcc67bb84c2ab2a89d79d21bac71"]`(ONLY_JAVA); `[id="947882db-ee5f-40df-8839-278e872b8774"]`(ONLY_GO); `[id="a72642611559442c8789b719fc42eed0"]`(ONLY_JAVA) …共 10 项 | 是 |
| trailtracks-info | `GET /base/trailtracks/e0e22490-fb40-4795-947b-68565d864aa7?uuid=e0e224` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-dataSource | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&dataSource=ZdTrails%` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-dataType | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&dataType=weigh` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-plateNo | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&plateNo=%E8%BD%A6%E7` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-siteId | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&siteId=4` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-list-order | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&orderByColumn=uuid&i` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| 404-deep | `GET /base/notatable/list` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 404-path | `GET /no/such/endpoint` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 405-info-delete | `DELETE /base/gantry/18` | DIFF | 405 | 405 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 405-list-post | `POST /base/gantry/list` | DIFF | 405 | 405 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| large-badtime | `GET /api/v1/large/snapshot?startTime=2025-10-01&endTime=abc&pageNum=1&` | DIFF | 200 | 200 | `code`(VALUE); `data`(KEY_ABSENT); `dataSource`(KEY_ABSENT); `message`(VALUE); `pageNum`(KEY_ABSENT); `pageSize`(KEY_ABSENT) | 否(重试后一致) |
| large-fee | `GET /api/v1/large/fee?startTime=2025-10-01+00%3A00%3A00&endTime=2025-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[bigId="1545746222"]`(ONLY_GO); `data[bigId="1545818359"]`(ONLY_GO); `data[bigId="1545892243"]`(ONLY_GO); `data[bigId="1547071182"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| large-trail | `GET /api/v1/large/trail?startTime=2025-10-01+00%3A00%3A00&endTime=2025` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[0]`(ONLY_GO); `data[1]`(ONLY_GO); `data[2]`(ONLY_GO); `data[3]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| unified-fee | `GET /api/v1/unified/fee/list?startTime=2025-10-01+00%3A00%3A00&endTime` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[bigId="1545746222"]`(ONLY_GO); `data[bigId="1545818359"]`(ONLY_GO); `data[bigId="1545892243"]`(ONLY_GO); `data[bigId="1547071182"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| unified-trail | `GET /api/v1/unified/trail/list?startTime=2025-10-01+00%3A00%3A00&endTi` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[0]`(ONLY_GO); `data[1]`(ONLY_GO); `data[2]`(ONLY_GO); `data[3]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| change-post | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailList[sectionCode=""]`(ONLY_GO); `trailList[sectionCode=null]`(ONLY_JAVA) | 否(重试后一致) |
| change-post-empty | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailUuid`(NULLISH) | 否(重试后一致) |
| change-post-notrail | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailUuid`(NULLISH) | 否(重试后一致) |
| getbytrailbo-t1 | `GET /base/sysutil/getByTrailBo?type=1&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t2 | `GET /base/sysutil/getByTrailBo?type=2&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t3 | `GET /base/sysutil/getByTrailBo?type=3&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t4 | `GET /base/sysutil/getByTrailBo?type=4&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t5 | `GET /base/sysutil/getByTrailBo?type=5&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t6 | `GET /base/sysutil/getByTrailBo?type=6&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t7 | `GET /base/sysutil/getByTrailBo?type=7&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t8 | `GET /base/sysutil/getByTrailBo?type=8&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-tempty | `GET /base/sysutil/getByTrailBo?type=&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| syncsuspicious-commented | `POST /base/sysutil/syncSuspiciousCar` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| synctrack-commented | `POST /base/sysutil/syncTrack` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| trailtracks-filter-enterTime | `GET /base/trailtracks/list?pageNum=1&pageSize=5&enterTime=2025-09-10+0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO); `rows[uuid="a204c869-e5cd-4c23-aa7f-073acc7c8056"]`(ONLY_GO); `rows[uuid="e0e22490-fb40-4795-947b-68565d864aa7"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| sql-ish-param | `GET /base/gantry/list?gantryName=O%27Brien&pageSize=5` | OK | 200 | 200 | - | 是 |
| type-mismatch | `GET /base/gantry/list?pageSize=abc` | OK | 200 | 200 | - | 是 |
| unicode-param | `GET /base/gantry/list?gantryName=%E7%91%9E%E9%87%91%E5%8C%97+%E4%BA%92` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_full | `POST /api/v1/large/sync/full` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_incremental | `POST /api/v1/large/sync/incremental` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_repair | `POST /api/v1/large/sync/repair` | OK | 400 | 400 | - | 是 |
| exists_base_sysutilTest_separateSnapshotFlowTimeList | `POST /base/sysutilTest/separateSnapshotFlowTimeList` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncBaseInfo | `POST /base/sysutilTest/syncBaseInfo` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncCurrentTrack | `POST /base/sysutilTest/syncCurrentTrack` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncHistroyTrack | `POST /base/sysutilTest/syncHistroyTrack` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncOdsSzdnGantry | `POST /base/sysutilTest/syncOdsSzdnGantry` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar | `POST /base/sysutilTest/syncSuspiciousCar` | OK | 404 | 404 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar1 | `POST /base/sysutilTest/syncSuspiciousCar1` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar10 | `POST /base/sysutilTest/syncSuspiciousCar10` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar2 | `POST /base/sysutilTest/syncSuspiciousCar2` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar3 | `POST /base/sysutilTest/syncSuspiciousCar3` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar4 | `POST /base/sysutilTest/syncSuspiciousCar4` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar5 | `POST /base/sysutilTest/syncSuspiciousCar5` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar6 | `POST /base/sysutilTest/syncSuspiciousCar6` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar7 | `POST /base/sysutilTest/syncSuspiciousCar7` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar8 | `POST /base/sysutilTest/syncSuspiciousCar8` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar9 | `POST /base/sysutilTest/syncSuspiciousCar9` | OK | 405 | 405 | - | 是 |
| exists_base_sysutil_saveRedis | `POST /base/sysutil/saveRedis` | OK | 405 | 405 | - | 是 |
| feeGantry-info | `GET /base/feeGantry/59?bigId=59` | OK | 200 | 200 | - | 是 |
| feeGantry-info-miss | `GET /base/feeGantry/__no_such_id__` | OK | 200 | 200 | both unparsable | 是 |
| feeGantry-list-pagesize-1 | `GET /base/feeGantry/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| feeGantry-list-pagesize0 | `GET /base/feeGantry/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-cardid | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&cardid=15012312232` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-electricalpercentage | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&electricalpercenta` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-enaxlecount | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&enaxlecount=2` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-entime | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&entime=2024-11-24` | OK | 200 | 200 | - | 是 |
| feeStationEnter-full-set | `GET /base/feeStationEnter/list?pageNum=1&pageSize=317` | OK | 200 | 200 | - | 是 |
| feeStationEnter-info | `GET /base/feeStationEnter/2308?bigId=2308` | OK | 200 | 200 | - | 是 |
| feeStationEnter-info-badid | `GET /base/feeStationEnter/not-a-number` | OK | 400 | 400 | - | 是 |
| feeStationEnter-info-miss | `GET /base/feeStationEnter/__no_such_id__` | OK | 400 | 400 | - | 是 |
| feeStationEnter-list-bigpagesize | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-default | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-farpage | `GET /base/feeStationEnter/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-noargs | `GET /base/feeStationEnter/list` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-order | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&orderByColumn=bigI` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-page2 | `GET /base/feeStationEnter/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-pagesize-1 | `GET /base/feeStationEnter/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-pagesize0 | `GET /base/feeStationEnter/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-actualfeeclass | `GET /base/feestationexit/list?pageNum=1&pageSize=5&actualfeeclass=0` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-axlecount | `GET /base/feestationexit/list?pageNum=1&pageSize=5&axlecount=2` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-discountfee | `GET /base/feestationexit/list?pageNum=1&pageSize=5&discountfee=0` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-electricalpercentage | `GET /base/feestationexit/list?pageNum=1&pageSize=5&electricalpercentag` | OK | 200 | 200 | - | 是 |
| feestationexit-full-set | `GET /base/feestationexit/list?pageNum=1&pageSize=270` | OK | 200 | 200 | - | 是 |
| feestationexit-info | `GET /base/feestationexit/11150377?bigId=11150377` | OK | 200 | 200 | - | 是 |
| feestationexit-info-miss | `GET /base/feestationexit/__no_such_id__` | OK | 200 | 200 | - | 是 |
| feestationexit-list-bigpagesize | `GET /base/feestationexit/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| feestationexit-list-default | `GET /base/feestationexit/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| feestationexit-list-farpage | `GET /base/feestationexit/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| feestationexit-list-noargs | `GET /base/feestationexit/list` | OK | 200 | 200 | - | 是 |
| feestationexit-list-order | `GET /base/feestationexit/list?pageNum=1&pageSize=5&orderByColumn=bigId` | OK | 200 | 200 | - | 是 |
| feestationexit-list-page2 | `GET /base/feestationexit/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| feestationexit-list-pagesize-1 | `GET /base/feestationexit/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| feestationexit-list-pagesize0 | `GET /base/feestationexit/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| fwqclls-filter-datauuid | `GET /manager/fwqclls/list?pageNum=1&pageSize=5&datauuid=uuid-fwq-20251` | OK | 200 | 200 | - | 是 |
| fwqclls-full-set | `GET /manager/fwqclls/list?pageNum=1&pageSize=3` | OK | 200 | 200 | - | 是 |
| fwqclls-info | `GET /manager/fwqclls/1?bigId=1` | OK | 200 | 200 | - | 是 |
| fwqclls-info-badid | `GET /manager/fwqclls/not-a-number` | OK | 400 | 400 | - | 是 |
| fwqclls-info-miss | `GET /manager/fwqclls/__no_such_id__` | OK | 400 | 400 | - | 是 |
| fwqclls-list-bigpagesize | `GET /manager/fwqclls/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| fwqclls-list-default | `GET /manager/fwqclls/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqclls-list-farpage | `GET /manager/fwqclls/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqclls-list-noargs | `GET /manager/fwqclls/list` | OK | 200 | 200 | - | 是 |
| fwqclls-list-order | `GET /manager/fwqclls/list?pageNum=1&pageSize=5&orderByColumn=bigId&isA` | OK | 200 | 200 | - | 是 |
| fwqclls-list-page2 | `GET /manager/fwqclls/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqclls-list-pagesize-1 | `GET /manager/fwqclls/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| fwqclls-list-pagesize0 | `GET /manager/fwqclls/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| fwqjcxx-filter-fwqbm | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&fwqbm=G0321361123W0010` | OK | 200 | 200 | - | 是 |
| fwqjcxx-filter-fwqmc | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&fwqmc=%E4%B8%89%E6%B8%85%E` | OK | 200 | 200 | - | 是 |
| fwqjcxx-full-set | `GET /base/fwqjcxx/list?pageNum=1&pageSize=218` | OK | 200 | 200 | - | 是 |
| fwqjcxx-info | `GET /base/fwqjcxx/1?agentPk=1` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-bigpagesize | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-default | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-farpage | `GET /base/fwqjcxx/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-noargs | `GET /base/fwqjcxx/list` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-order | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-page2 | `GET /base/fwqjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-pagesize-1 | `GET /base/fwqjcxx/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-pagesize0 | `GET /base/fwqjcxx/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| fwqjcxx-listAll | `GET /base/fwqjcxx/listAll` | OK | 200 | 200 | - | 是 |
| gantry-filter-gantryCode | `GET /base/gantry/list?pageNum=1&pageSize=5&gantryCode=G003536012000720` | OK | 200 | 200 | - | 是 |
| gantry-filter-gantryName | `GET /base/gantry/list?pageNum=1&pageSize=5&gantryName=%E7%91%9E%E9%87%` | OK | 200 | 200 | - | 是 |
| gantry-filter-roadCode | `GET /base/gantry/list?pageNum=1&pageSize=5&roadCode=G35` | OK | 200 | 200 | - | 是 |
| gantry-filter-sectionCode | `GET /base/gantry/list?pageNum=1&pageSize=5&sectionCode=200R50035072900` | OK | 200 | 200 | - | 是 |
| gantry-full-set | `GET /base/gantry/list?pageNum=1&pageSize=1526` | OK | 200 | 200 | - | 是 |
| gantry-info | `GET /base/gantry/18?id=18` | OK | 200 | 200 | - | 是 |
| gantry-info-miss | `GET /base/gantry/__no_such_id__` | OK | 200 | 200 | - | 是 |
| gantry-list-bigpagesize | `GET /base/gantry/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| gantry-list-default | `GET /base/gantry/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantry-list-farpage | `GET /base/gantry/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantry-list-noargs | `GET /base/gantry/list` | OK | 200 | 200 | - | 是 |
| gantry-list-order | `GET /base/gantry/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=desc` | OK | 200 | 200 | - | 是 |
| gantry-list-page2 | `GET /base/gantry/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantry-list-pagesize-1 | `GET /base/gantry/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| gantry-list-pagesize0 | `GET /base/gantry/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| gantry-listAll | `GET /base/gantry/listAll` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-gantryCode | `GET /base/gantryIp/list?pageNum=1&pageSize=5&gantryCode=S0036360110005` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-gantryName | `GET /base/gantryIp/list?pageNum=1&pageSize=5&gantryName=%E5%8D%97%E5%A` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-ip | `GET /base/gantryIp/list?pageNum=1&pageSize=5&ip=36.121.3.43` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-orgCode | `GET /base/gantryIp/list?pageNum=1&pageSize=5&orgCode=020000253` | OK | 200 | 200 | - | 是 |
| gantryIp-full-set | `GET /base/gantryIp/list?pageNum=1&pageSize=1033` | OK | 200 | 200 | - | 是 |
| gantryIp-info | `GET /base/gantryIp/1?id=1` | OK | 200 | 200 | - | 是 |
| gantryIp-info-badid | `GET /base/gantryIp/not-a-number` | OK | 400 | 400 | - | 是 |
| gantryIp-info-miss | `GET /base/gantryIp/__no_such_id__` | OK | 400 | 400 | - | 是 |
| gantryIp-list-bigpagesize | `GET /base/gantryIp/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| gantryIp-list-default | `GET /base/gantryIp/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantryIp-list-farpage | `GET /base/gantryIp/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantryIp-list-noargs | `GET /base/gantryIp/list` | OK | 200 | 200 | - | 是 |
| gantryIp-list-order | `GET /base/gantryIp/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=de` | OK | 200 | 200 | - | 是 |
| gantryIp-list-page2 | `GET /base/gantryIp/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantryIp-list-pagesize-1 | `GET /base/gantryIp/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| gantryIp-list-pagesize0 | `GET /base/gantryIp/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| org-filter-orgCode | `GET /base/org/list?pageNum=1&pageSize=5&orgCode=000000936` | OK | 200 | 200 | - | 是 |
| org-filter-orgName | `GET /base/org/list?pageNum=1&pageSize=5&orgName=%E4%B8%AD%E5%BF%83%E6%` | OK | 200 | 200 | - | 是 |
| org-filter-orgParentId | `GET /base/org/list?pageNum=1&pageSize=5&orgParentId=030000009` | OK | 200 | 200 | - | 是 |
| org-filter-orgShortName | `GET /base/org/list?pageNum=1&pageSize=5&orgShortName=%E4%B8%AD%E5%BF%8` | OK | 200 | 200 | - | 是 |
| org-full-set | `GET /base/org/list?pageNum=1&pageSize=481` | OK | 200 | 200 | - | 是 |
| org-info | `GET /base/org/24945?bigId=24945` | OK | 200 | 200 | - | 是 |
| org-info-miss | `GET /base/org/__no_such_id__` | OK | 200 | 200 | - | 是 |
| org-list-bigpagesize | `GET /base/org/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| org-list-default | `GET /base/org/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-list-farpage | `GET /base/org/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-list-noargs | `GET /base/org/list` | OK | 200 | 200 | - | 是 |
| org-list-order | `GET /base/org/list?pageNum=1&pageSize=5&orderByColumn=bigId&isAsc=desc` | OK | 200 | 200 | - | 是 |
| org-list-page2 | `GET /base/org/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-list-pagesize-1 | `GET /base/org/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| org-list-pagesize0 | `GET /base/org/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| org-listAll | `GET /base/org/listAll` | OK | 200 | 200 | - | 是 |
| provcapture-filter-deviceip | `GET /base/provcapture/list?pageNum=1&pageSize=5&deviceip=36.101.189.5` | OK | 200 | 200 | - | 是 |
| provcapture-filter-platecolorcode | `GET /base/provcapture/list?pageNum=1&pageSize=5&platecolorcode=1` | OK | 200 | 200 | - | 是 |
| provcapture-filter-tailcapturetime | `GET /base/provcapture/list?pageNum=1&pageSize=5&tailcapturetime=1969-1` | OK | 200 | 200 | - | 是 |
| provcapture-filter-tailcapturetimeunix | `GET /base/provcapture/list?pageNum=1&pageSize=5&tailcapturetimeunix=-2` | OK | 200 | 200 | - | 是 |
| provcapture-full-set | `GET /base/provcapture/list?pageNum=1&pageSize=356` | OK | 200 | 200 | - | 是 |
| provcapture-info | `GET /base/provcapture/312748?bigId=312748` | OK | 200 | 200 | - | 是 |
| provcapture-info-badid | `GET /base/provcapture/not-a-number` | OK | 400 | 400 | - | 是 |
| provcapture-info-miss | `GET /base/provcapture/__no_such_id__` | OK | 400 | 400 | - | 是 |
| provcapture-list-bigpagesize | `GET /base/provcapture/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| provcapture-list-default | `GET /base/provcapture/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| provcapture-list-farpage | `GET /base/provcapture/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| provcapture-list-noargs | `GET /base/provcapture/list` | OK | 200 | 200 | - | 是 |
| provcapture-list-order | `GET /base/provcapture/list?pageNum=1&pageSize=5&orderByColumn=bigId&is` | OK | 200 | 200 | - | 是 |
| provcapture-list-page2 | `GET /base/provcapture/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| provcapture-list-pagesize-1 | `GET /base/provcapture/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| provcapture-list-pagesize0 | `GET /base/provcapture/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| export-status-unknown | `GET /api/v1/large/export/status/nope` | OK | 200 | 200 | - | 是 |
| large-cartrack | `GET /api/v1/large/carTrackQueryByCarNo?carNo=%E8%B5%A3AF12345&startTim` | OK | 200 | 200 | - | 是 |
| large-fuzzy | `GET /api/v1/large/snapshot?startTime=2025-10-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| large-missing-arg | `GET /api/v1/large/snapshot?endTime=2025-10-02+00%3A00%3A00` | OK | 400 | 400 | - | 是 |
| large-snapshot | `GET /api/v1/large/snapshot?startTime=2025-10-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| large-stats | `GET /api/v1/large/stats/group?type=snapshot&startTime=2025-10-01+00%3A` | OK | 200 | 200 | - | 是 |
| large-stats-badgroup | `GET /api/v1/large/stats/group?type=snapshot&startTime=2025-10-01+00%3A` | OK | 200 | 200 | - | 是 |
| large-window-huge | `GET /api/v1/large/snapshot?startTime=2025-09-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| prog-filter | `GET /progressive/snapshotflow/list?startTime=2025-10-01+00%3A00%3A00&e` | OK | 200 | 200 | - | 是 |
| prog-noargs | `GET /progressive/snapshotflow/list` | OK | 200 | 200 | - | 是 |
| prog-scalelevel | `GET /progressive/scale-level` | OK | 200 | 200 | - | 是 |
| prog-snapshotflow | `GET /progressive/snapshotflow/list?startTime=2025-10-01+00%3A00%3A00&e` | OK | 200 | 200 | - | 是 |
| unified-baddb | `GET /api/v1/unified/__nope__/list?startTime=2025-10-01+00%3A00%3A00&en` | OK | 200 | 200 | - | 是 |
| unified-export-status-unknown | `GET /api/v1/unified/export/status/nope` | OK | 200 | 200 | - | 是 |
| unified-snapshot | `GET /api/v1/unified/snapshot/list?startTime=2025-10-01+00%3A00%3A00&en` | OK | 200 | 200 | - | 是 |
| section-filter-roadCode | `GET /base/section/list?pageNum=1&pageSize=5&roadCode=G6021` | OK | 200 | 200 | - | 是 |
| section-filter-roadName | `GET /base/section/list?pageNum=1&pageSize=5&roadName=%E6%9D%AD%E9%95%B` | OK | 200 | 200 | - | 是 |
| section-filter-sectionCode | `GET /base/section/list?pageNum=1&pageSize=5&sectionCode=200R5602106710` | OK | 200 | 200 | - | 是 |
| section-filter-sectionName | `GET /base/section/list?pageNum=1&pageSize=5&sectionName=%E4%B9%90%E6%B` | OK | 200 | 200 | - | 是 |
| section-full-set | `GET /base/section/list?pageNum=1&pageSize=85` | OK | 200 | 200 | - | 是 |
| section-info | `GET /base/section/18?id=18` | OK | 200 | 200 | - | 是 |
| section-info-miss | `GET /base/section/__no_such_id__` | OK | 200 | 200 | - | 是 |
| section-list-bigpagesize | `GET /base/section/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| section-list-default | `GET /base/section/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| section-list-farpage | `GET /base/section/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| section-list-noargs | `GET /base/section/list` | OK | 200 | 200 | - | 是 |
| section-list-order | `GET /base/section/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=des` | OK | 200 | 200 | - | 是 |
| section-list-page2 | `GET /base/section/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| section-list-pagesize-1 | `GET /base/section/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| section-list-pagesize0 | `GET /base/section/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| section-listAll | `GET /base/section/listAll` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-jd | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&jd=117.43187400` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-sfsmc | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&sfsmc=%E4%B8%8A%E4%B8%87%E` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-yxtzj | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&yxtzj=1531950771411013633` | OK | 200 | 200 | - | 是 |
| sfsjcxx-full-set | `GET /base/sfsjcxx/list?pageNum=1&pageSize=24` | OK | 200 | 200 | - | 是 |
| sfsjcxx-info | `GET /base/sfsjcxx/d2c6df4afa7ff18d48786d728d3919d2?agentPk=d2c6df4afa7` | OK | 200 | 200 | - | 是 |
| sfsjcxx-info-miss | `GET /base/sfsjcxx/__no_such_id__` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-bigpagesize | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-default | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-farpage | `GET /base/sfsjcxx/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-noargs | `GET /base/sfsjcxx/list` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-order | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-page2 | `GET /base/sfsjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-pagesize-1 | `GET /base/sfsjcxx/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-pagesize0 | `GET /base/sfsjcxx/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| sfsjcxx-listAll | `GET /base/sfsjcxx/listAll` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-agentPk | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&agentPk=363bc7b76e508c55dc` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-sfzdm | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&sfzdm=G56360429F0010` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-sfzmc | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&sfzmc=%E5%9D%87%E6%A1%A5%E` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-yxtzj | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&yxtzj=1495673117678645249` | OK | 200 | 200 | - | 是 |
| sfzjcxx-full-set | `GET /base/sfzjcxx/list?pageNum=1&pageSize=320` | OK | 200 | 200 | - | 是 |
| sfzjcxx-info | `GET /base/sfzjcxx/363bc7b76e508c55dcb259cf6a3f007e?agentPk=363bc7b76e5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-info-miss | `GET /base/sfzjcxx/__no_such_id__` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-bigpagesize | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-default | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-farpage | `GET /base/sfzjcxx/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-noargs | `GET /base/sfzjcxx/list` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-order | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-page2 | `GET /base/sfzjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-pagesize-1 | `GET /base/sfzjcxx/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-pagesize0 | `GET /base/sfzjcxx/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| sfzjcxx-listAll | `GET /base/sfzjcxx/listAll` | OK | 200 | 200 | - | 是 |
| snapshotflow-info | `GET /base/snapshotflow/f249ade5f48041cc983c4b0232fa8c2f?bigId=f249ade5` | OK | 200 | 200 | both unparsable | 是 |
| snapshotflow-info-miss | `GET /base/snapshotflow/__no_such_id__` | OK | 200 | 200 | both unparsable | 是 |
| snapshotflow-list-pagesize-1 | `GET /base/snapshotflow/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| snapshotflow-list-pagesize0 | `GET /base/snapshotflow/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-cameratype | `GET /base/stationcapture/list?pageNum=1&pageSize=5&cameratype=StationC` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-datasource | `GET /base/stationcapture/list?pageNum=1&pageSize=5&datasource=ZdTrails` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-deviceid | `GET /base/stationcapture/list?pageNum=1&pageSize=5&deviceid=00000000` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-deviceip | `GET /base/stationcapture/list?pageNum=1&pageSize=5&deviceip=36.105.104` | OK | 200 | 200 | - | 是 |
| stationcapture-full-set | `GET /base/stationcapture/list?pageNum=1&pageSize=851` | OK | 200 | 200 | - | 是 |
| stationcapture-info | `GET /base/stationcapture/20113483?bigId=20113483` | OK | 200 | 200 | - | 是 |
| stationcapture-info-badid | `GET /base/stationcapture/not-a-number` | OK | 400 | 400 | - | 是 |
| stationcapture-info-miss | `GET /base/stationcapture/__no_such_id__` | OK | 400 | 400 | - | 是 |
| stationcapture-list-bigpagesize | `GET /base/stationcapture/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| stationcapture-list-default | `GET /base/stationcapture/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| stationcapture-list-farpage | `GET /base/stationcapture/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| stationcapture-list-noargs | `GET /base/stationcapture/list` | OK | 200 | 200 | - | 是 |
| stationcapture-list-order | `GET /base/stationcapture/list?pageNum=1&pageSize=5&orderByColumn=bigId` | OK | 200 | 200 | - | 是 |
| stationcapture-list-page2 | `GET /base/stationcapture/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| stationcapture-list-pagesize-1 | `GET /base/stationcapture/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| stationcapture-list-pagesize0 | `GET /base/stationcapture/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| cartrack-blank | `GET /base/sysutil/carTrackQueryByCarNo?plateNo=&pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| cartrack-by-carno | `GET /base/sysutil/carTrackQueryByCarNo?plateNo=%E8%B5%A3AF12345&startT` | OK | 400 | 400 | - | 是 |
| cartrack-by-time | `GET /base/sysutil/carTrackQueryByTime?startTime=2025-10-01+00%3A00%3A0` | OK | 400 | 400 | - | 是 |
| toll-filter-idCard | `GET /base/toll/list?pageNum=1&pageSize=5&idCard=44L4464527980850000` | OK | 200 | 200 | - | 是 |
| toll-filter-roadCode | `GET /base/toll/list?pageNum=1&pageSize=5&roadCode=S43` | OK | 200 | 200 | - | 是 |
| toll-filter-tollCode | `GET /base/toll/list?pageNum=1&pageSize=5&tollCode=S43361002F0020` | OK | 200 | 200 | - | 是 |
| toll-filter-tollName | `GET /base/toll/list?pageNum=1&pageSize=5&tollName=%E6%8A%9A%E5%B7%9E%E` | OK | 200 | 200 | - | 是 |
| toll-full-set | `GET /base/toll/list?pageNum=1&pageSize=321` | OK | 200 | 200 | - | 是 |
| toll-info | `GET /base/toll/1?id=1` | OK | 200 | 200 | - | 是 |
| toll-info-miss | `GET /base/toll/__no_such_id__` | OK | 200 | 200 | - | 是 |
| toll-list-bigpagesize | `GET /base/toll/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| toll-list-default | `GET /base/toll/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-list-farpage | `GET /base/toll/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-list-noargs | `GET /base/toll/list` | OK | 200 | 200 | - | 是 |
| toll-list-order | `GET /base/toll/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=desc` | OK | 200 | 200 | - | 是 |
| toll-list-page2 | `GET /base/toll/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-list-pagesize-1 | `GET /base/toll/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| toll-list-pagesize0 | `GET /base/toll/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| toll-listAll | `GET /base/toll/listAll` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-ip | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&ip=36.106.145.9` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-orgCode | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&orgCode=030000008` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-tollCode | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&tollCode=S0089360020` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-tollName | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&tollName=%E8%8E%B2%E` | OK | 200 | 200 | - | 是 |
| tollStationIp-full-set | `GET /base/tollStationIp/list?pageNum=1&pageSize=302` | OK | 200 | 200 | - | 是 |
| tollStationIp-info | `GET /base/tollStationIp/40017?id=40017` | OK | 200 | 200 | - | 是 |
| tollStationIp-info-badid | `GET /base/tollStationIp/not-a-number` | OK | 400 | 400 | - | 是 |
| tollStationIp-info-miss | `GET /base/tollStationIp/__no_such_id__` | OK | 400 | 400 | - | 是 |
| tollStationIp-list-bigpagesize | `GET /base/tollStationIp/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-default | `GET /base/tollStationIp/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-farpage | `GET /base/tollStationIp/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-noargs | `GET /base/tollStationIp/list` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-order | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&orderByColumn=id&isA` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-page2 | `GET /base/tollStationIp/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-pagesize-1 | `GET /base/tollStationIp/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-pagesize0 | `GET /base/tollStationIp/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| trailtracks-filter-plateKey | `GET /base/trailtracks/list?pageNum=1&pageSize=5&plateKey=%E8%B5%A3CEA8` | OK | 200 | 200 | - | 是 |
| trailtracks-filter-pointCount | `GET /base/trailtracks/list?pageNum=1&pageSize=5&pointCount=45` | OK | 200 | 200 | - | 是 |
| trailtracks-filter-type | `GET /base/trailtracks/list?pageNum=1&pageSize=5&type=0` | OK | 200 | 200 | - | 是 |
| trailtracks-full-set | `GET /base/trailtracks/list?pageNum=1&pageSize=1379` | OK | 200 | 200 | - | 是 |
| trailtracks-info-miss | `GET /base/trailtracks/__no_such_id__` | OK | 200 | 200 | - | 是 |
| trailtracks-list-bigpagesize | `GET /base/trailtracks/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| trailtracks-list-default | `GET /base/trailtracks/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| trailtracks-list-farpage | `GET /base/trailtracks/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| trailtracks-list-noargs | `GET /base/trailtracks/list` | OK | 200 | 200 | - | 是 |
| trailtracks-list-order | `GET /base/trailtracks/list?pageNum=1&pageSize=5&orderByColumn=uuid&isA` | OK | 200 | 200 | - | 是 |
| trailtracks-list-page2 | `GET /base/trailtracks/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| trailtracks-list-pagesize-1 | `GET /base/trailtracks/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| trailtracks-list-pagesize0 | `GET /base/trailtracks/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| vehicleweight-full-set | `GET /base/vehicleweight/list?pageNum=1&pageSize=300` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-bigpagesize | `GET /base/vehicleweight/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-default | `GET /base/vehicleweight/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-farpage | `GET /base/vehicleweight/list?pageNum=99999&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-noargs | `GET /base/vehicleweight/list` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-page2 | `GET /base/vehicleweight/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-pagesize-1 | `GET /base/vehicleweight/list?pageNum=1&pageSize=-1` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-pagesize0 | `GET /base/vehicleweight/list?pageNum=1&pageSize=0` | OK | 200 | 200 | - | 是 |
| vehicleweight-map | `GET /base/vehicleweight/map` | OK | 200 | 200 | - | 是 |

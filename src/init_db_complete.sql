-- UDI 医疗器械唯一标识数据
-- 官方架构中的业务值全部是字符型；这里只对数量、版本号和日期做语义化存储。

CREATE TABLE IF NOT EXISTS udi_devices (
    device_record_key VARCHAR(128) NOT NULL COMMENT '官方记录 key，稳定关联同一条公开记录',
    zxxsdycpbs VARCHAR(128) NULL COMMENT '最小销售单元产品标识',
    cpbsbmtxmc VARCHAR(128) NULL COMMENT '医疗器械唯一标识编码体系名称',
    cpbsfbrq DATE NULL COMMENT '产品标识发布日期',
    cpbsfbrq_raw VARCHAR(64) NULL COMMENT '产品标识发布日期原文',
    zxxsdyzsydydsl BIGINT UNSIGNED NULL COMMENT '最小销售单元中使用单元的数量',
    sydycpbs VARCHAR(128) NULL COMMENT '使用单元产品标识',
    bszt VARCHAR(256) NULL COMMENT '标识载体',
    sfyzcbayz VARCHAR(16) NULL COMMENT '是否与注册/备案产品标识一致',
    zcbacpbs VARCHAR(128) NULL COMMENT '注册/备案产品标识',
    sfybtzjbs VARCHAR(16) NULL COMMENT '是否有本体标识',
    btcpbsyzxxsdycpbssfyz VARCHAR(16) NULL COMMENT '本体产品标识与最小销售单元产品标识是否一致',
    btcpbs VARCHAR(128) NULL COMMENT '本体产品标识',
    cpmctymc VARCHAR(1024) NULL COMMENT '产品名称或通用名称',
    spmc VARCHAR(1024) NULL COMMENT '商品名称',
    ggxh VARCHAR(2048) NULL COMMENT '规格型号',
    sfwblztlcp VARCHAR(16) NULL COMMENT '是否为包类/组套类产品',
    cpms TEXT NULL COMMENT '产品描述',
    cphhhbh VARCHAR(1024) NULL COMMENT '产品货号或编号',
    yflbm VARCHAR(128) NULL COMMENT '原分类编码',
    qxlb VARCHAR(32) NULL COMMENT '器械类别',
    flbm VARCHAR(128) NULL COMMENT '分类编码',
    tyshxydm VARCHAR(64) NULL COMMENT '企业统一社会信用代码，按字符串保存',
    zczbhhzbapzbh VARCHAR(2048) NULL COMMENT '注册证编号或者备案凭证编号',
    ylqxzcrbarmc VARCHAR(1024) NULL COMMENT '医疗器械注册人/备案人名称',
    ylqxzcrbarywmc VARCHAR(1024) NULL COMMENT '医疗器械注册人/备案人英文名称',
    ybbm VARCHAR(1024) NULL COMMENT '医保耗材分类编码',
    cplb VARCHAR(32) NULL COMMENT '产品类别',
    cgzmraqxgxx TEXT NULL COMMENT '磁共振（MR）安全相关信息',
    sfbjwycxsy VARCHAR(16) NULL COMMENT '是否标记为一次性使用',
    zdcfsycs BIGINT UNSIGNED NULL COMMENT '最大重复使用次数',
    sfwwjbz VARCHAR(16) NULL COMMENT '是否为无菌包装',
    syqsfxyjxmj VARCHAR(16) NULL COMMENT '使用前是否需要进行灭菌',
    mjfs VARCHAR(1024) NULL COMMENT '灭菌方式',
    qtxxdwzlj VARCHAR(2048) NULL COMMENT '其他信息的网址链接',
    tsrq DATE NULL COMMENT '退市日期',
    tsrq_raw VARCHAR(64) NULL COMMENT '退市日期原文',
    scbssfbhph VARCHAR(16) NULL COMMENT '生产标识是否包含批号',
    scbssfbhxlh VARCHAR(16) NULL COMMENT '生产标识是否包含序列号',
    scbssfbhscrq VARCHAR(16) NULL COMMENT '生产标识是否包含生产日期',
    scbssfbhsxrq VARCHAR(16) NULL COMMENT '生产标识是否包含失效日期',
    tscchcztj TEXT NULL COMMENT '特殊储存或操作条件',
    tsccsm TEXT NULL COMMENT '特殊尺寸说明',
    version_number INT UNSIGNED NULL COMMENT '公开版本号',
    version_time DATETIME NULL COMMENT '版本发布时间',
    version_time_raw VARCHAR(64) NULL COMMENT '版本发布时间原文',
    version_status VARCHAR(32) NULL COMMENT '版本状态；XML 官方标签拼写为 versionStauts',
    correction_number INT UNSIGNED NULL COMMENT '纠错次数',
    correction_remark TEXT NULL COMMENT '纠错说明',
    correction_time DATETIME NULL COMMENT '纠错时间',
    correction_time_raw VARCHAR(64) NULL COMMENT '纠错时间原文',
    has_packing_list TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否有包装列表',
    has_storage_list TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否有储存条件列表',
    has_clinical_list TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否有临床尺寸列表',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (device_record_key),
    KEY idx_zxxsdycpbs (zxxsdycpbs),
    KEY idx_cpmctymc (cpmctymc(191)),
    KEY idx_tyshxydm (tyshxydm),
    KEY idx_flbm (flbm),
    KEY idx_version_time (version_time),
    KEY idx_version_status (version_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI 当前公开版本设备主表';

CREATE TABLE IF NOT EXISTS udi_packing_list (
    device_record_key VARCHAR(128) NOT NULL,
    item_no INT UNSIGNED NOT NULL COMMENT '源 XML 中的列表顺序，从 1 开始',
    bzcpbs VARCHAR(128) NULL COMMENT '包装产品标识',
    cpbzjb VARCHAR(64) NULL COMMENT '产品包装级别',
    bznhxyjcpbssl BIGINT UNSIGNED NULL COMMENT '包装内含小一级产品标识数量',
    bznhxyjbzcpbs VARCHAR(128) NULL COMMENT '包装内含小一级包装产品标识',
    PRIMARY KEY (device_record_key, item_no),
    KEY idx_bzcpbs (bzcpbs)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI 包装产品标识信息';

CREATE TABLE IF NOT EXISTS udi_storage_list (
    device_record_key VARCHAR(128) NOT NULL,
    item_no INT UNSIGNED NOT NULL COMMENT '源 XML 中的列表顺序，从 1 开始',
    cchcztj VARCHAR(1024) NULL COMMENT '储存或操作条件',
    zdz VARCHAR(128) NULL COMMENT '最低值，保留字符串以支持区间或非数值表达',
    zgz VARCHAR(128) NULL COMMENT '最高值，保留字符串以支持区间或非数值表达',
    jldw VARCHAR(64) NULL COMMENT '计量单位',
    PRIMARY KEY (device_record_key, item_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI 特殊储存或操作条件信息';

CREATE TABLE IF NOT EXISTS udi_clinical_list (
    device_record_key VARCHAR(128) NOT NULL,
    item_no INT UNSIGNED NOT NULL COMMENT '源 XML 中的列表顺序，从 1 开始',
    lcsycclx VARCHAR(1024) NULL COMMENT '临床使用尺寸类型',
    ccz VARCHAR(256) NULL COMMENT '尺寸值，保留字符串以支持复合尺寸',
    ccdw VARCHAR(64) NULL COMMENT '尺寸单位',
    PRIMARY KEY (device_record_key, item_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI 临床尺寸信息';

CREATE TABLE IF NOT EXISTS udi_contacts (
    device_record_key VARCHAR(128) NOT NULL,
    item_no INT UNSIGNED NOT NULL COMMENT '源 XML 中的列表顺序，从 1 开始',
    qylxrcz VARCHAR(128) NULL COMMENT '企业联系人传真',
    qylxryx VARCHAR(320) NULL COMMENT '企业联系人邮箱',
    qylxrdh VARCHAR(128) NULL COMMENT '企业联系人电话',
    PRIMARY KEY (device_record_key, item_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI 企业联系信息';

CREATE TABLE IF NOT EXISTS import_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL COMMENT 'completed 或 failed',
    total_records BIGINT UNSIGNED NOT NULL DEFAULT 0,
    success_records BIGINT UNSIGNED NOT NULL DEFAULT 0,
    failed_records BIGINT UNSIGNED NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    duration_seconds INT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_import_logs_created_at (created_at),
    KEY idx_import_logs_file_name (file_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='导入结果日志';

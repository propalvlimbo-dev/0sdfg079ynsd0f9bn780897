package com.ticxo.modelengine.api.utils.config;
public class ConfigCache { public boolean isUseNewRotation(){return Boolean.parseBoolean(System.getProperty("modelengine.test.rotation", "true"));} }

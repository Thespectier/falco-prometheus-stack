import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, message, Space, Typography } from 'antd';
import { SaveOutlined, SettingOutlined } from '@ant-design/icons';
import { api } from '../api/client';

const { Title, Text } = Typography;

/**
 * 大模型配置的表单项。
 *
 * `secret` 的项用密码框：读取接口只回掩码，用户不填就保持原值不变。
 */
const LLM_FIELDS = [
  {
    label: 'API Endpoint',
    name: 'endpoint',
    placeholder: 'https://api.deepseek.com',
    required: true,
    requiredMessage: 'Please enter API endpoint',
    secret: false,
  },
  {
    label: 'Model Name',
    name: 'model',
    placeholder: 'deepseek-chat',
    required: true,
    requiredMessage: 'Please enter model name',
    secret: false,
  },
  {
    label: 'API Key',
    name: 'api_key',
    placeholder: 'Leave empty to keep unchanged',
    required: false,
    requiredMessage: 'Please enter API key',
    secret: true,
  },
];

/**
 * 载入配置并处理保存。
 *
 * 保存后回读一次：后端会把 api_key 掩码后再返回，这样界面上不会留着刚输入的明文，
 * 用户也能立刻看到当前生效的值。
 */
function useLLMConfigForm(form: ReturnType<typeof Form.useForm>[0]) {
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await api.getLLMConfig();
        form.setFieldsValue(config);
      } catch (error) {
        message.error('Failed to load settings');
      }
    };
    loadConfig();
  }, [form]);

  const save = async (values: any) => {
    setSaving(true);
    try {
      await api.setLLMConfig(values);
      message.success('Settings saved successfully');
      const config = await api.getLLMConfig();
      form.setFieldsValue(config);
    } catch (error) {
      message.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return { saving, save };
}

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const { saving, save } = useLLMConfigForm(form);

  return (
    <div style={{ padding: '24px', maxWidth: 800, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Space align="center" style={{ marginBottom: 24 }}>
            <SettingOutlined style={{ fontSize: 24, color: '#1890ff' }} />
            <Title level={3} style={{ margin: 0 }}>System Settings</Title>
          </Space>

          <Card title="LLM Configuration (Analyzer)" type="inner">
            <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
              Configure the Large Language Model settings used for analyzing security incidents.
              Changes will be picked up by the analyzer service within 10 seconds.
            </Text>

            <Form
              form={form}
              layout="vertical"
              onFinish={save}
              initialValues={{
                endpoint: 'https://api.deepseek.com',
                model: 'deepseek-chat'
              }}
            >
              {LLM_FIELDS.map((field) => (
                <Form.Item
                  key={field.name}
                  label={field.label}
                  name={field.name}
                  rules={[{ required: field.required, message: field.requiredMessage }]}
                >
                  {field.secret
                    ? <Input.Password placeholder={field.placeholder} />
                    : <Input placeholder={field.placeholder} />}
                </Form.Item>
              ))}

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
                  Save Configuration
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Card>
      </Space>
    </div>
  );
};

export default Settings;

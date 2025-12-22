import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, message, Space, Typography } from 'antd';
import { SaveOutlined, SettingOutlined } from '@ant-design/icons';
import { api } from '../api/client';

const { Title, Text } = Typography;

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const config = await api.getLLMConfig();
        form.setFieldsValue(config);
      } catch (error) {
        message.error('Failed to load settings');
      }
    };
    fetchConfig();
  }, [form]);

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      await api.setLLMConfig(values);
      message.success('Settings saved successfully');
    } catch (error) {
      message.error('Failed to save settings');
    } finally {
      setLoading(false);
    }
  };

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
              onFinish={onFinish}
              initialValues={{
                endpoint: 'https://api.deepseek.com',
                model: 'deepseek-chat'
              }}
            >
              <Form.Item
                label="API Endpoint"
                name="endpoint"
                rules={[{ required: true, message: 'Please enter API endpoint' }]}
              >
                <Input placeholder="https://api.deepseek.com" />
              </Form.Item>

              <Form.Item
                label="Model Name"
                name="model"
                rules={[{ required: true, message: 'Please enter model name' }]}
              >
                <Input placeholder="deepseek-chat" />
              </Form.Item>

              <Form.Item
                label="API Key"
                name="api_key"
                rules={[{ required: true, message: 'Please enter API key' }]}
              >
                <Input.Password placeholder="sk-..." />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>
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

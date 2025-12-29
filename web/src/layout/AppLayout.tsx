import React from 'react';
import { Layout, Menu, theme } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { DashboardOutlined, FileTextOutlined, AlertOutlined, ApartmentOutlined, SafetyCertificateOutlined, SettingOutlined } from '@ant-design/icons';

const { Header, Content, Sider } = Layout;

const AppLayout: React.FC = () => {
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: 'Overview',
    },
    {
      key: '/hbt',
      icon: <ApartmentOutlined />,
      label: 'Behavior Tree (HBT)',
    },
    {
      key: '/logs',
      icon: <FileTextOutlined />,
      label: 'Container Logs',
    },
    {
      key: '/alerts',
      icon: <AlertOutlined />,
      label: 'Alerts',
    },
    {
      key: '/incidents',
      icon: <SafetyCertificateOutlined />,
      label: 'Incidents',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: 'Settings',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0">
        <div style={{ 
          height: 64, 
          margin: 16, 
          background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)', 
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: 16,
          fontWeight: 'bold',
          letterSpacing: 0.5,
          textAlign: 'center',
          padding: '0 12px',
          lineHeight: 1.2,
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
        }}>
          基础设施攻击识别与响应工具
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: colorBgContainer }} />
        <Content style={{ margin: '24px 16px 0' }}>
          <div
            style={{
              padding: 24,
              minHeight: 360,
              background: colorBgContainer,
              borderRadius: borderRadiusLG,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;

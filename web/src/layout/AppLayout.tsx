import React from 'react';
import { Layout, Menu, theme } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AlertOutlined, ApartmentOutlined, DashboardOutlined, FileTextOutlined, SafetyCertificateOutlined, SettingOutlined } from '@ant-design/icons';

const { Header, Content, Sider } = Layout;

/**
 * 侧栏导航项。
 *
 * `key` 就是路由路径：改动这里必须同步 `App.tsx` 的 `Route path`，否则点进去会落到
 * 兜底路由。顺序即展示顺序。
 */
const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'Overview' },
  { key: '/hbt', icon: <ApartmentOutlined />, label: 'Behavior Tree (HBT)' },
  { key: '/logs', icon: <FileTextOutlined />, label: 'Container Logs' },
  { key: '/alerts', icon: <AlertOutlined />, label: 'Alerts' },
  { key: '/incidents', icon: <SafetyCertificateOutlined />, label: 'Incidents' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings' },
];

/** 品牌区样式：渐变底 + 居中标题，高度与侧栏折叠断点配合 */
const BRAND_STYLE: React.CSSProperties = {
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
};

/** 内容区留白：上留 24px 与页头分隔，卡片本身再各留 24px 内边距 */
const CONTENT_STYLE: React.CSSProperties = { margin: '24px 16px 0' };

const AppLayout: React.FC = () => {
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0">
        <div style={BRAND_STYLE}>
          基础设施攻击识别与响应工具
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: colorBgContainer }} />
        <Content style={CONTENT_STYLE}>
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

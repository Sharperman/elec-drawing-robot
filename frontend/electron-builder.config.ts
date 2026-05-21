import type { Configuration } from 'electron-builder';

const config: Configuration = {
  appId: 'com.elecdrawing.robot',
  productName: '电气图纸绘制机器人',
  directories: {
    output: 'release',
    buildResources: 'public',
  },
  files: [
    'dist/**/*',
    'dist-electron/**/*',
  ],
  extraResources: [
    {
      from: '../backend',
      to: 'backend',
      filter: ['**/*', '!**/__pycache__/**', '!**/*.pyc'],
    },
    {
      from: '../requirements.txt',
      to: 'requirements.txt',
    },
  ],
  win: {
    target: [
      { target: 'nsis', arch: ['x64'] },
    ],
    icon: 'public/icon.ico',
    requestedExecutionLevel: 'requireAdministrator',
  },
  nsis: {
    oneClick: false,
    allowToChangeInstallationDirectory: true,
    installerIcon: 'public/icon.ico',
    uninstallerIcon: 'public/icon.ico',
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
  },
  mac: {
    target: 'dmg',
    icon: 'public/icon.icns',
  },
  linux: {
    target: 'AppImage',
    icon: 'public/icon.png',
  },
};

export default config;

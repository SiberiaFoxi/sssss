// ClanSecrets: a diagnostics + own-data window for DerenguhGram (tdesktop).
// SPDX-License-Identifier: GPL-3.0-only
//
// Tabs:
//   * Logs      — network connections, errors, version, proxy status.
//   * Cache     — cache folder path, "open folder", a browser of YOUR OWN cache.
//   * ClanSecrets — an export folder for media YOU are allowed to keep.
//
// Privacy note: this window deliberately does NOT capture other people's
// self-destructing / view-once media. That defeats a protection the sender enabled
// and can facilitate non-consensual retention. Instead it offers a consent-respecting
// "request a permanent copy" action and exports only non-protected content.
#pragma once

#include <QDialog>
#include <QString>

class QPlainTextEdit;
class QLineEdit;
class QListWidget;
class QLabel;

namespace derenguh {

class ClanSecretsWindow : public QDialog {
    Q_OBJECT
public:
    explicit ClanSecretsWindow(QWidget *parent = nullptr);

    // Called by the network/proxy layer to surface diagnostics.
    void appendLog(const QString &line);
    void setProxyStatus(const QString &status);
    void setVersionInfo(const QString &version);
    void setCachePath(const QString &path);

private slots:
    void openCacheFolder();
    void refreshCacheList();
    void openExportFolder();
    void requestPermanentCopy();

private:
    QWidget *buildLogsTab();
    QWidget *buildCacheTab();
    QWidget *buildSecretsTab();

    QPlainTextEdit *_logs = nullptr;
    QLabel *_proxyStatus = nullptr;
    QLabel *_version = nullptr;
    QLineEdit *_cachePath = nullptr;
    QListWidget *_cacheList = nullptr;
    QString _exportDir;
};

} // namespace derenguh

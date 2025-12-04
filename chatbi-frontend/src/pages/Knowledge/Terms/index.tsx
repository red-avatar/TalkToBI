import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BookOpen, RefreshCw, Plus, Edit2, Trash2, X } from 'lucide-react';
import { Card, Button, Spinner } from '../../../components/ui';
import { termsApi } from '../../../api/terms';
import type { BusinessTerm, CreateTermRequest, UpdateTermRequest } from '../../../api/types';
import * as styles from './styles.css';

interface ModalState {
  open: boolean;
  mode: 'create' | 'edit';
  term?: BusinessTerm;
}

const Terms: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [terms, setTerms] = useState<BusinessTerm[]>([]);
  const [modal, setModal] = useState<ModalState>({ open: false, mode: 'create' });
  const [form, setForm] = useState({ name: '', meaning: '', sql_hint: '', examples: '' });
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await termsApi.getList();
      setTerms(res.data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const openCreateModal = () => {
    setForm({ name: '', meaning: '', sql_hint: '', examples: '' });
    setModal({ open: true, mode: 'create' });
  };

  const openEditModal = (term: BusinessTerm) => {
    setForm({ name: term.name, meaning: term.meaning, sql_hint: term.sql_hint || '', examples: (term.examples || []).join('\n') });
    setModal({ open: true, mode: 'edit', term });
  };

  const closeModal = () => setModal({ open: false, mode: 'create' });

  const handleSave = async () => {
    if (!form.name || !form.meaning) return;
    setSaving(true);
    try {
      const examples = form.examples.split('\n').map(s => s.trim()).filter(Boolean);
      if (modal.mode === 'create') {
        const data: CreateTermRequest = { name: form.name, meaning: form.meaning, sql_hint: form.sql_hint || undefined, examples: examples.length > 0 ? examples : undefined };
        await termsApi.create(data);
      } else {
        const data: UpdateTermRequest = { meaning: form.meaning, sql_hint: form.sql_hint || undefined, examples: examples.length > 0 ? examples : undefined };
        await termsApi.update(modal.term!.name, data);
      }
      closeModal();
      loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`确定删除名词 "​${name}" 吗？`)) return;
    try {
      await termsApi.delete(name);
      loadData();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <motion.div className={styles.container} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <BookOpen size={28} color="#BD00FF" />
          <h1 className={styles.title}>业务名词</h1>
        </div>
        <div className={styles.headerRight}>
          <Button variant="ghost" size="sm" leftIcon={loading ? <Spinner size="sm" /> : <RefreshCw size={16} />} onClick={loadData} disabled={loading}>刷新</Button>
          <Button size="sm" leftIcon={<Plus size={16} />} onClick={openCreateModal}>添加名词</Button>
        </div>
      </div>

      {/* Table */}
      <Card variant="glass" padding="md">
        {loading ? (
          <div className={styles.emptyState}><Spinner size="lg" /></div>
        ) : terms.length === 0 ? (
          <div className={styles.emptyState}>
            <BookOpen size={48} color="rgba(255,255,255,0.2)" />
            <p>暂无业务名词，点击上方按钮添加</p>
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>名词</th>
                  <th>含义</th>
                  <th>SQL 提示</th>
                  <th>示例</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {terms.map((t) => (
                  <tr key={t.name}>
                    <td className={styles.nameCell}>{t.name}</td>
                    <td className={styles.meaningCell}>{t.meaning}</td>
                    <td>{t.sql_hint ? <code className={styles.sqlHint}>{t.sql_hint}</code> : '-'}</td>
                    <td>
                      <div className={styles.examplesList}>
                        {(t.examples || []).slice(0, 3).map((ex, i) => (<span key={i} className={styles.exampleTag}>{ex}</span>))}
                        {(t.examples?.length || 0) > 3 && <span className={styles.exampleTag}>+{t.examples!.length - 3}</span>}
                      </div>
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <Button variant="ghost" size="sm" leftIcon={<Edit2 size={14} />} onClick={() => openEditModal(t)} />
                        <Button variant="ghost" size="sm" leftIcon={<Trash2 size={14} />} onClick={() => handleDelete(t.name)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className={styles.pageInfo}>共 {terms.length} 个业务名词</p>
      </Card>

      {/* Modal */}
      <AnimatePresence>
        {modal.open && (
          <motion.div className={styles.modalOverlay} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={closeModal}>
            <motion.div className={styles.modalContent} onClick={(e) => e.stopPropagation()} initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}>
              <Card variant="glass" padding="lg">
                <div className={styles.modalHeader}>
                  <h3 className={styles.modalTitle}>{modal.mode === 'create' ? '添加业务名词' : '编辑业务名词'}</h3>
                  <Button variant="ghost" size="sm" leftIcon={<X size={18} />} onClick={closeModal} />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>名词名称 *</label>
                  <input className={styles.formInput} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：GMV、DAU" disabled={modal.mode === 'edit'} />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>含义解释 *</label>
                  <textarea className={styles.formTextarea} value={form.meaning} onChange={(e) => setForm({ ...form, meaning: e.target.value })} placeholder="详细解释该名词的业务含义" />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>SQL 提示</label>
                  <input className={styles.formInput} value={form.sql_hint} onChange={(e) => setForm({ ...form, sql_hint: e.target.value })} placeholder="如：SUM(order_amount)" />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>示例问题 (每行一个)</label>
                  <textarea className={styles.formTextarea} value={form.examples} onChange={(e) => setForm({ ...form, examples: e.target.value })} placeholder="今年GMV多少\n各月GMV趋势" />
                </div>
                <div className={styles.modalFooter}>
                  <Button variant="ghost" onClick={closeModal}>取消</Button>
                  <Button onClick={handleSave} disabled={saving || !form.name || !form.meaning}>{saving ? <Spinner size="sm" /> : '保存'}</Button>
                </div>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default Terms;

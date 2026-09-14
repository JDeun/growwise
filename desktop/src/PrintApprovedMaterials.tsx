function PrintApprovedMaterials() {
  function handlePrint() {
    const approved = document.querySelector(".material-card .status-approved");
    if (!approved) {
      window.alert("현재 아이에 승인된 자료가 없습니다.");
      return;
    }
    window.print();
  }

  return (
    <aside className="print-toolbar" aria-label="자료 내보내기">
      <button className="quiet-button" type="button" onClick={handlePrint}>
        승인 자료 PDF·인쇄
      </button>
      <span>승인된 자료만 인쇄 화면에 포함됩니다.</span>
    </aside>
  );
}

export default PrintApprovedMaterials;

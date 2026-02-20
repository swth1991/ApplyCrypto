import com.samsunglife.dcp.cms.params.CmsParameters;
import com.samsunglife.dcp.core.exception.DataAccessException;

/**
 * 서비스현황_상담신청 DAO
 * @author gwanghoon.kim
 */
@Repository
public class SrvcPnstacNclDao {

    private static final String NAMESPACE = "dcms.srvcpnsta.";

    @Resource(name = "sqlDaoSession")
    protected SqlSession sqlDaoSession;

    /**
     * 서비스현황_상담신청 기준일자 조회
     * @param parameters
     * @return
     * @throws DataAccessException
     */
    public List<SrvcPnstacDaoModel> selectMonimoSrvcPnstacNclStandDate(CmsParameters parameters) throws DataAccessException {
        return sqlDaoSession.selectList(NAMESPACE + "selectMonimoSrvcPnstacStandDate", parameters);
    }

    /**
     * 서비스현황_상담신청 채널 조회
     * @param parameters
     * @return
     * @throws DataAccessException
     */
    public List<SrvcPnstacDaoModel> selectMonimoSrvcPnstacNclChnl(CmsParameters parameters) throws DataAccessException {
        return sqlDaoSession.selectList(NAMESPACE + "selectMonimoSrvcPnstacChnl", parameters);
    }

    /**
     * 서비스현황_상담신청 목록 조회
     * @param parameters
     * @return
     * @throws DataAccessException
     */
    public List<SrvcPnstacDaoModel> selectMonimoSrvcPnstacNclList(CmsParameters parameters) throws DataAccessException {
        return sqlDaoSession.selectList(NAMESPACE + "selectMonimoSrvcPnstacNcl", parameters);
    }
}
